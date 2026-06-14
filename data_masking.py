"""
Data Masking Module - Bidirectional PII Masking for LLM Gateway
Masks sensitive data in prompts before sending to LLM, unmasks in responses
Supports both streaming and non-streaming responses

Three-Layer Pipeline Architecture:
  Layer 1: Built-in Regex (email, phone, SSN, etc.)
  Layer 2: Local SLM Semantic Detection (optional, with graceful degradation)
  Layer 3: Custom Keywords (absolute confidential terms)

Multimodal Extensions:
  - OCR-based image scanning (EasyOCR)
  - Pixel-level blackout box masking (Pillow)
"""

import re
import json
import base64
import io
import logging
import httpx
from typing import Dict, Tuple, List, Optional, AsyncIterator, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
try:
    from PIL import Image, ImageDraw, ImageFont
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    logger.warning("[DataMasker] Pillow not available - image masking disabled")

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False
    logger.warning("[DataMasker] EasyOCR not available - image masking disabled")

try:
    from faker import Faker
    FAKER_AVAILABLE = True
except ImportError:
    FAKER_AVAILABLE = False
    logger.warning("[DataMasker] Faker not available - pseudonymization disabled")

try:
    import ahocorasick
    AHOCORASICK_AVAILABLE = True
except ImportError:
    AHOCORASICK_AVAILABLE = False
    logger.warning("[DataMasker] pyahocorasick not available - stream unmasking will use regex fallback")


# ======================== Data Structures ========================

@dataclass
class MaskingRule:
    """Single masking rule configuration"""
    name: str
    pattern: str
    entity_type: str
    compiled_regex: re.Pattern = field(init=False)

    def __post_init__(self):
        """Compile regex pattern after initialization"""
        try:
            self.compiled_regex = re.compile(self.pattern)
        except re.error as e:
            logger.error(f"Invalid regex pattern in rule '{self.name}': {e}")
            # Fallback to a pattern that never matches
            self.compiled_regex = re.compile(r'(?!.*)')


@dataclass
class MaskingStore:
    """
    Request-specific masking store with pseudonymization support
    Maintains bidirectional mapping between real values and fake pseudonyms
    """
    # Pseudonym mappings (real ↔ fake)
    real_to_fake: Dict[str, str] = field(default_factory=dict)
    fake_to_real: Dict[str, str] = field(default_factory=dict)

    # Legacy placeholder mappings (for backward compatibility)
    mask_to_original: Dict[str, str] = field(default_factory=dict)
    original_to_mask: Dict[str, str] = field(default_factory=dict)
    entity_counters: Dict[str, int] = field(default_factory=dict)

    def add_pseudonym_mapping(self, real_value: str, fake_value: str):
        """Add bidirectional pseudonym mapping"""
        self.real_to_fake[real_value] = fake_value
        self.fake_to_real[fake_value] = real_value

    def get_fake(self, real_value: str) -> Optional[str]:
        """Get fake pseudonym from real value"""
        return self.real_to_fake.get(real_value)

    def get_real(self, fake_value: str) -> Optional[str]:
        """Get real value from fake pseudonym"""
        return self.fake_to_real.get(fake_value)

    def add_mapping(self, original: str, mask: str):
        """Add bidirectional mapping (legacy placeholder support)"""
        self.mask_to_original[mask] = original
        self.original_to_mask[original] = mask

    def get_original(self, mask: str) -> Optional[str]:
        """Get original value from mask (legacy)"""
        return self.mask_to_original.get(mask)

    def get_mask(self, original: str) -> Optional[str]:
        """Get mask from original value (legacy)"""
        return self.original_to_mask.get(original)

    def next_counter(self, entity_type: str) -> int:
        """Get next counter for entity type"""
        counter = self.entity_counters.get(entity_type, 0)
        self.entity_counters[entity_type] = counter + 1
        return counter


# ======================== DataMasker Core Class ========================

class DataMasker:
    """
    Core data masking engine with three-layer pipeline + pseudonymization
    Layer 1: Built-in Regex -> Layer 2: Local SLM -> Layer 3: Custom Keywords

    Pseudonymization Mode: Uses Faker to generate semantic-preserving fake names
    instead of obvious placeholders like [MASK_0]
    """

    def __init__(self, config: dict):
        """
        Initialize DataMasker with configuration

        Args:
            config: Data masking configuration from config.yaml
        """
        self.enabled = config.get('enabled', False)
        self.rules: List[MaskingRule] = []
        self.custom_keywords: List[str] = []

        # Layer 2: Local SLM configuration
        self.slm_enabled = False
        self.slm_base_url = None
        self.slm_model = None
        self.slm_timeout = 0.5
        self.is_slm_available = False

        # Multimodal: Image masking configuration
        self.mask_images = config.get('mask_images', False)
        self.ocr_reader = None

        # Pseudonymization: Faker instances for different locales
        self.use_pseudonyms = config.get('use_pseudonyms', True) and FAKER_AVAILABLE
        self.faker_zh = None
        self.faker_en = None

        if self.use_pseudonyms and FAKER_AVAILABLE:
            self.faker_zh = Faker('zh_CN')
            self.faker_en = Faker('en_US')
            # Set consistent seed for reproducibility within same session
            self.faker_zh.seed_instance(42)
            self.faker_en.seed_instance(42)
            logger.info("[DataMasker] Pseudonymization mode enabled (Faker)")
        elif config.get('use_pseudonyms', True) and not FAKER_AVAILABLE:
            logger.warning("[DataMasker] Pseudonymization requested but Faker unavailable, falling back to placeholders")
            self.use_pseudonyms = False

        if not self.enabled:
            logger.info("[DataMasker] Data masking disabled")
            return

        # Load Layer 1: Built-in regex rules
        rules_config = config.get('rules', [])
        for rule_dict in rules_config:
            rule = MaskingRule(
                name=rule_dict['name'],
                pattern=rule_dict['pattern'],
                entity_type=rule_dict['entity_type']
            )
            self.rules.append(rule)

        # Load Layer 3: Custom keywords
        self.custom_keywords = config.get('custom_keywords', [])

        # Load Layer 2: Local SLM config
        slm_config = config.get('local_slm', {})
        self.slm_enabled = slm_config.get('enabled', False)
        self.slm_base_url = slm_config.get('base_url')
        self.slm_model = slm_config.get('model', 'qwen2.5:0.5b-instruct')
        self.slm_timeout = slm_config.get('timeout', 0.5)

        logger.info(f"[DataMasker] Initialized with {len(self.rules)} regex rules, "
                   f"{len(self.custom_keywords)} custom keywords, "
                   f"image_masking={'enabled' if self.mask_images else 'disabled'}")

        # Initialize OCR reader if image masking is enabled
        if self.mask_images and EASYOCR_AVAILABLE and PILLOW_AVAILABLE:
            try:
                logger.info("[DataMasker] Initializing EasyOCR reader (ch_sim, en)...")
                self.ocr_reader = easyocr.Reader(['ch_sim', 'en'], gpu=False, verbose=False)
                logger.info("[DataMasker] OCR reader initialized successfully")
            except Exception as e:
                logger.warning(f"[DataMasker] Failed to initialize OCR reader: {e}")
                self.mask_images = False
        elif self.mask_images:
            logger.warning("[DataMasker] Image masking enabled but dependencies missing (Pillow/EasyOCR)")
            self.mask_images = False

        # Health check for local SLM
        if self.slm_enabled and self.slm_base_url:
            self._check_slm_availability()
        else:
            logger.info("[DataMasker] Local SLM disabled in config")

    def _check_slm_availability(self):
        """
        Health check for local SLM endpoint
        Sets is_slm_available flag based on connectivity
        """
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{self.slm_base_url}/models")
                if response.status_code == 200:
                    self.is_slm_available = True
                    logger.info(f"[DataMasker] Local SLM health check passed: {self.slm_base_url}")
                else:
                    self._log_slm_unavailable(f"Health check failed (status: {response.status_code})")
        except Exception as e:
            self._log_slm_unavailable(f"Connection error: {e}")

    def _log_slm_unavailable(self, reason: str):
        """Log SLM unavailability warning"""
        logger.warning(
            f"\033[93m[Data Masking] Local SLM is unavailable or disabled. "
            f"Guard Layer 2 will be skipped (Graceful Degradation active). "
            f"Reason: {reason}\033[0m"
        )
        self.is_slm_available = False

    def _generate_pseudonym(self, original_text: str, entity_type: str) -> str:
        """
        Generate semantic-preserving pseudonym using Faker

        Args:
            original_text: Original sensitive value
            entity_type: Type of entity (email, phone, person_name, etc.)

        Returns:
            Fake but realistic replacement value
        """
        if not self.use_pseudonyms:
            # Fallback to placeholder mode
            return None

        try:
            # Detect language: Chinese vs English
            is_chinese = bool(re.search(r'[一-鿿]', original_text))
            faker = self.faker_zh if is_chinese else self.faker_en

            # Generate appropriate fake data based on entity type
            if entity_type == 'email':
                return faker.email()
            elif entity_type == 'phone':
                return faker.phone_number()
            elif entity_type == 'person_name':
                return faker.name()
            elif entity_type == 'chinese_id':
                # Chinese ID: generate realistic fake format
                return self.faker_zh.ssn() if self.faker_zh else f"110101199001011234"
            elif entity_type == 'ssn':
                # US SSN
                return self.faker_en.ssn()
            elif entity_type == 'ip_address':
                return faker.ipv4()
            elif entity_type in ['slm', 'keyword']:
                # For semantic entities and keywords: generate project-like codenames
                return f"Project_{faker.word().capitalize()}"
            else:
                # Generic fallback
                return faker.word().capitalize()

        except Exception as e:
            logger.warning(f"[DataMasker] Pseudonym generation failed: {e}")
            return None

    def _extract_sensitive_words_via_slm(self, text: str) -> List[str]:
        """
        Layer 2: Extract semantically sensitive words using local SLM

        Args:
            text: Text to analyze (already processed by Layer 1)

        Returns:
            List of detected sensitive phrases
        """
        if not self.is_slm_available:
            return []

        system_prompt = (
            "你是一个专职的数据脱敏助手。请分析用户的输入，找出其中所有可能属于商业机密、"
            "核心技术代号、未公开产品名、个人隐私特征（如特定人名、特殊公司名）的实体短语。"
            "必须严格以 JSON 字符串数组格式返回这些短语，不要包含任何解释、不要 Markdown 格式。"
            "例如: [\"秘密代号A\", \"研发部内部协议\"]"
        )

        try:
            with httpx.Client(timeout=self.slm_timeout) as client:
                response = client.post(
                    f"{self.slm_base_url}/chat/completions",
                    json={
                        "model": self.slm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": text}
                        ],
                        "temperature": 0.1,
                        "max_tokens": 200
                    }
                )

                if response.status_code != 200:
                    logger.warning(f"[DataMasker] SLM request failed (status: {response.status_code})")
                    return []

                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Parse JSON array from response
                sensitive_words = json.loads(content)
                if isinstance(sensitive_words, list):
                    logger.debug(f"[DataMasker] SLM detected {len(sensitive_words)} sensitive entities")
                    return [str(word) for word in sensitive_words]
                else:
                    logger.warning(f"[DataMasker] SLM returned non-list response: {content}")
                    return []

        except json.JSONDecodeError as e:
            logger.warning(f"[DataMasker] SLM response not valid JSON: {e}")
            return []
        except httpx.TimeoutException:
            logger.warning(f"[DataMasker] SLM request timeout ({self.slm_timeout}s)")
            return []
        except Exception as e:
            logger.warning(f"[DataMasker] SLM extraction failed: {e}")
            return []

    def mask_prompt(self, text: str, store: Optional[MaskingStore] = None) -> Tuple[str, MaskingStore]:
        """
        Three-layer masking pipeline with pseudonymization:
          1. Built-in Regex (email, phone, SSN, etc.)
          2. Local SLM Semantic Detection (optional)
          3. Custom Keywords (absolute confidential terms)

        Pseudonymization: Replaces sensitive values with realistic fake data (Faker)
        instead of obvious placeholders like [MASK_0]

        Args:
            text: Original prompt text
            store: Optional existing MaskingStore to reuse (for multi-message requests)

        Returns:
            Tuple of (masked_text, masking_store)
        """
        if not self.enabled or not text:
            return text, store or MaskingStore()

        # Use provided store or create new one
        if store is None:
            store = MaskingStore()

        masked_text = text

        # ============ Layer 1: Built-in Regex Rules ============
        for rule in self.rules:
            matches = list(rule.compiled_regex.finditer(masked_text))

            # Process matches in reverse order to preserve positions
            for match in reversed(matches):
                original_value = match.group(0)

                # Check if already masked in store (pseudonym mapping)
                if original_value in store.real_to_fake:
                    # Reuse existing pseudonym
                    replacement = store.get_fake(original_value)
                else:
                    # Generate new pseudonym or placeholder
                    replacement = self._generate_pseudonym(original_value, rule.entity_type)

                    if replacement is None:
                        # Fallback to placeholder mode
                        counter = store.next_counter(rule.entity_type)
                        replacement = f"[MASK_{rule.entity_type.upper()}_{counter}]"
                        store.add_mapping(original_value, replacement)
                    else:
                        # Store pseudonym mapping
                        store.add_pseudonym_mapping(original_value, replacement)

                # Replace in text
                start, end = match.span()
                masked_text = masked_text[:start] + replacement + masked_text[end:]

        # ============ Layer 2: Local SLM Semantic Detection ============
        if self.is_slm_available:
            try:
                sensitive_words = self._extract_sensitive_words_via_slm(masked_text)

                for word in sensitive_words:
                    if not word or len(word.strip()) == 0:
                        continue

                    # Check if already masked
                    if word in store.real_to_fake:
                        replacement = store.get_fake(word)
                    else:
                        # Generate pseudonym for semantic entity
                        replacement = self._generate_pseudonym(word, 'slm')

                        if replacement is None:
                            # Fallback to placeholder
                            counter = store.next_counter('slm')
                            replacement = f"[MASK_SLM_{counter}]"
                            store.add_mapping(word, replacement)
                        else:
                            store.add_pseudonym_mapping(word, replacement)

                    # Replace all occurrences
                    masked_text = masked_text.replace(word, replacement)

            except Exception as e:
                logger.warning(f"[DataMasker] Layer 2 (SLM) failed, continuing: {e}")

        # ============ Layer 3: Custom Keywords ============
        for keyword in self.custom_keywords:
            if not keyword:
                continue

            # Check if already masked
            if keyword in store.real_to_fake:
                replacement = store.get_fake(keyword)
            else:
                # Generate pseudonym for keyword
                replacement = self._generate_pseudonym(keyword, 'keyword')

                if replacement is None:
                    # Fallback to placeholder
                    counter = store.next_counter('keyword')
                    replacement = f"[MASK_KEYWORD_{counter}]"
                    store.add_mapping(keyword, replacement)
                else:
                    store.add_pseudonym_mapping(keyword, replacement)

            # Case-insensitive replacement
            masked_text = re.sub(
                re.escape(keyword),
                replacement,
                masked_text,
                flags=re.IGNORECASE
            )

        total_masked = len(store.real_to_fake) + len(store.mask_to_original)
        logger.debug(f"[DataMasker] Masked {total_masked} entities "
                    f"(Pseudonyms: {len(store.real_to_fake)}, Placeholders: {len(store.mask_to_original)})")
        return masked_text, store

    def unmask_text(self, text: str, store: MaskingStore) -> str:
        """
        Unmask text using masking store (non-streaming)
        Supports both pseudonym mapping and legacy placeholder mode

        Args:
            text: Masked text (with pseudonyms or placeholders)
            store: Masking store from mask_prompt

        Returns:
            Unmasked text with original values restored
        """
        if not self.enabled:
            return text

        unmasked_text = text

        # Step 1: Replace pseudonyms with real values
        if store.fake_to_real:
            # Sort by length (longest first) to avoid partial matches
            sorted_fakes = sorted(store.fake_to_real.keys(), key=len, reverse=True)
            for fake_value in sorted_fakes:
                real_value = store.fake_to_real[fake_value]
                unmasked_text = unmasked_text.replace(fake_value, real_value)

        # Step 2: Replace legacy placeholders with original values
        if store.mask_to_original:
            for mask_placeholder, original_value in store.mask_to_original.items():
                unmasked_text = unmasked_text.replace(mask_placeholder, original_value)

        return unmasked_text

    def mask_multimodal_inputs(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Scan and mask sensitive information in multimodal messages (text + images)

        Args:
            messages: OpenAI/Claude format message array

        Returns:
            Modified messages with masked images
        """
        if not self.enabled or not self.mask_images or not self.ocr_reader:
            return messages

        modified_messages = []

        for message in messages:
            # Deep copy to avoid modifying original
            modified_message = json.loads(json.dumps(message))

            # Check if content is multimodal (array format)
            content = modified_message.get('content')
            if not isinstance(content, list):
                modified_messages.append(modified_message)
                continue

            # Process each content block
            for i, block in enumerate(content):
                if not isinstance(block, dict):
                    continue

                # Check for image_url blocks
                if block.get('type') == 'image_url':
                    image_url_data = block.get('image_url', {})
                    url = image_url_data.get('url', '')

                    # Check if it's a base64 data URL
                    if url.startswith('data:image/'):
                        try:
                            masked_url = self._mask_image_base64(url)
                            modified_message['content'][i]['image_url']['url'] = masked_url
                            logger.info(f"[DataMasker] Masked image in message (index {i})")
                        except Exception as e:
                            logger.warning(f"[DataMasker] Failed to mask image: {e}")

            modified_messages.append(modified_message)

        return modified_messages

    def _mask_image_base64(self, data_url: str) -> str:
        """
        Mask sensitive information in base64-encoded image

        Args:
            data_url: Data URL format (data:image/png;base64,...)

        Returns:
            Modified data URL with blackout boxes over sensitive text
        """
        # Step A: Decode base64 to image
        try:
            # Parse data URL
            header, base64_data = data_url.split(',', 1)
            image_format = header.split('/')[1].split(';')[0]  # png, jpeg, etc.

            # Decode base64
            image_bytes = base64.b64decode(base64_data)
            image = Image.open(io.BytesIO(image_bytes))

            # Step B: OCR scan
            logger.debug(f"[DataMasker] Running OCR on {image.size} image...")
            ocr_results = self.ocr_reader.readtext(image)

            # Step C: Check for sensitive text
            redactions = []  # List of bounding boxes to redact
            for detection in ocr_results:
                bbox, text, confidence = detection
                # bbox format: [[x0, y0], [x1, y1], [x2, y2], [x3, y3]]

                if confidence < 0.3:  # Skip low-confidence detections
                    continue

                # Check against Layer 1 (regex rules)
                is_sensitive = False
                for rule in self.rules:
                    if rule.compiled_regex.search(text):
                        logger.info(f"[DataMasker] OCR detected sensitive text (regex): '{text}'")
                        is_sensitive = True
                        break

                # Check against Layer 3 (custom keywords)
                if not is_sensitive:
                    for keyword in self.custom_keywords:
                        if keyword.lower() in text.lower():
                            logger.info(f"[DataMasker] OCR detected sensitive text (keyword): '{text}'")
                            is_sensitive = True
                            break

                if is_sensitive:
                    redactions.append(bbox)

            # Step D: Draw blackout boxes
            if redactions:
                logger.info(f"[DataMasker] Applying {len(redactions)} blackout boxes")
                draw = ImageDraw.Draw(image)

                for bbox in redactions:
                    # Convert bbox to rectangle coordinates
                    # bbox: [[x0,y0], [x1,y1], [x2,y2], [x3,y3]]
                    xs = [point[0] for point in bbox]
                    ys = [point[1] for point in bbox]
                    x_min, x_max = min(xs), max(xs)
                    y_min, y_max = min(ys), max(ys)

                    # Add padding
                    padding = 5
                    x_min = max(0, x_min - padding)
                    y_min = max(0, y_min - padding)
                    x_max = min(image.width, x_max + padding)
                    y_max = min(image.height, y_max + padding)

                    # Draw black rectangle
                    draw.rectangle(
                        [(x_min, y_min), (x_max, y_max)],
                        fill='black',
                        outline='black'
                    )

            # Step E: Re-encode to base64
            output_buffer = io.BytesIO()
            save_format = 'PNG' if image_format.lower() == 'png' else 'JPEG'
            image.save(output_buffer, format=save_format)
            output_buffer.seek(0)

            new_base64 = base64.b64encode(output_buffer.read()).decode('utf-8')
            new_data_url = f"data:image/{image_format};base64,{new_base64}"

            return new_data_url

        except Exception as e:
            logger.error(f"[DataMasker] Image masking error: {e}")
            # Return original on error
            return data_url


# ======================== Streaming Unmasker ========================

class StreamUnmasker:
    """
    Streaming unmasker with Aho-Corasick multi-pattern matching
    Handles both pseudonyms (natural text) and legacy placeholders

    Uses sliding window buffer to detect fake values being streamed character-by-character,
    then replaces them with real values before yielding to client
    """

    def __init__(self, store: MaskingStore):
        """
        Initialize StreamUnmasker

        Args:
            store: Masking store from mask_prompt
        """
        self.store = store
        self.buffer = ""
        self.automaton = None

        # Build Aho-Corasick automaton if available
        if AHOCORASICK_AVAILABLE:
            self._build_automaton()
        else:
            # Fallback: use regex for placeholders only
            self.mask_pattern = re.compile(r'\[MASK_[A-Z_]+_\d+\]')
            logger.warning("[StreamUnmasker] Using regex fallback (pyahocorasick not available)")

    def _build_automaton(self):
        """Build Aho-Corasick automaton for all fake values (pseudonyms + placeholders)"""
        if not AHOCORASICK_AVAILABLE:
            return

        self.automaton = ahocorasick.Automaton()

        # Add all fake values (pseudonyms) from store
        for fake_value, real_value in self.store.fake_to_real.items():
            self.automaton.add_word(fake_value, (fake_value, real_value))

        # Add all legacy placeholders
        for mask_placeholder, original_value in self.store.mask_to_original.items():
            self.automaton.add_word(mask_placeholder, (mask_placeholder, original_value))

        # Build finite state machine
        if len(self.automaton) > 0:
            self.automaton.make_automaton()
            logger.debug(f"[StreamUnmasker] Built Aho-Corasick automaton with {len(self.automaton)} patterns")
        else:
            self.automaton = None

    async def unmask_stream(self, chunk_iterator: AsyncIterator[str]) -> AsyncIterator[str]:
        """
        Unmask streaming chunks using Aho-Corasick or regex fallback

        Args:
            chunk_iterator: Async iterator of text chunks from upstream LLM

        Yields:
            Unmasked text chunks with real values
        """
        if AHOCORASICK_AVAILABLE and self.automaton:
            async for chunk in self._unmask_stream_ahocorasick(chunk_iterator):
                yield chunk
        else:
            async for chunk in self._unmask_stream_regex_fallback(chunk_iterator):
                yield chunk

    async def _unmask_stream_ahocorasick(self, chunk_iterator: AsyncIterator[str]) -> AsyncIterator[str]:
        """
        Unmask using Aho-Corasick algorithm for multi-pattern matching

        Strategy:
        1. Accumulate chunks in buffer
        2. Use Aho-Corasick to find all fake value matches in buffer
        3. If match ends at buffer boundary, wait for more chunks (could be partial)
        4. Otherwise, replace and yield safe prefix
        """
        last_safe_pos = 0  # Position up to which we can safely yield

        async for chunk in chunk_iterator:
            self.buffer += chunk

            # Find all matches in current buffer
            matches = []
            for end_pos, (fake_value, real_value) in self.automaton.iter(self.buffer):
                start_pos = end_pos - len(fake_value) + 1
                matches.append((start_pos, end_pos + 1, fake_value, real_value))

            if not matches:
                # No matches found, check if buffer ends with partial match
                max_fake_len = max(
                    [len(f) for f in self.store.fake_to_real.keys()] +
                    [len(m) for m in self.store.mask_to_original.keys()],
                    default=0
                )

                # Keep last N characters in buffer (where N = max pattern length)
                safe_len = max(0, len(self.buffer) - max_fake_len)
                if safe_len > 0:
                    yield self.buffer[:safe_len]
                    self.buffer = self.buffer[safe_len:]
            else:
                # Process matches, replace fake with real
                result = []
                pos = 0

                for start, end, fake_value, real_value in matches:
                    # Append text before match
                    result.append(self.buffer[pos:start])
                    # Append real value
                    result.append(real_value)
                    pos = end

                # Yield up to last complete match
                last_match_end = matches[-1][1]

                # Check if last match ends at buffer boundary (might be partial)
                if last_match_end == len(self.buffer):
                    # Could be partial match, keep buffer tail
                    max_fake_len = max(
                        [len(f) for f in self.store.fake_to_real.keys()] +
                        [len(m) for m in self.store.mask_to_original.keys()],
                        default=0
                    )
                    safe_output = ''.join(result[:-1])  # Exclude last replacement
                    if safe_output:
                        yield safe_output
                    # Keep last match and tail in buffer
                    self.buffer = self.buffer[matches[-2][1] if len(matches) > 1 else 0:]
                else:
                    # Safe to yield everything up to last match
                    yield ''.join(result)
                    self.buffer = self.buffer[last_match_end:]

        # Flush remaining buffer (apply final replacement if any matches)
        if self.buffer:
            # One final pass
            result = self.buffer
            for fake_value, real_value in self.store.fake_to_real.items():
                result = result.replace(fake_value, real_value)
            for mask_placeholder, original_value in self.store.mask_to_original.items():
                result = result.replace(mask_placeholder, original_value)
            yield result

    async def _unmask_stream_regex_fallback(self, chunk_iterator: AsyncIterator[str]) -> AsyncIterator[str]:
        """
        Fallback unmasking using regex (legacy placeholder mode only)
        Used when pyahocorasick is not available
        """
        async for chunk in chunk_iterator:
            # Add chunk to buffer
            self.buffer += chunk

            # Try to extract and unmask complete placeholders
            while True:
                # Check if buffer contains potential mask start
                bracket_pos = self.buffer.find('[')

                if bracket_pos == -1:
                    # No potential mask in buffer, release everything
                    if self.buffer:
                        yield self.buffer
                        self.buffer = ""
                    break

                # Release text before bracket
                if bracket_pos > 0:
                    yield self.buffer[:bracket_pos]
                    self.buffer = self.buffer[bracket_pos:]

                # Try to match complete mask placeholder
                match = self.mask_pattern.match(self.buffer)

                if match:
                    # Complete mask found
                    mask_placeholder = match.group(0)
                    original_value = self.store.get_original(mask_placeholder)

                    if original_value:
                        # Unmask and release
                        yield original_value
                    else:
                        # Unknown mask, release as-is
                        yield mask_placeholder

                    # Remove mask from buffer
                    self.buffer = self.buffer[match.end():]
                else:
                    # Check if buffer could be incomplete mask
                    if self._could_be_mask_prefix(self.buffer):
                        # Wait for more chunks
                        break
                    else:
                        # Not a valid mask, release the bracket and continue
                        yield self.buffer[0]
                        self.buffer = self.buffer[1:]

        # Flush remaining buffer
        if self.buffer:
            yield self.buffer

    def _could_be_mask_prefix(self, text: str) -> bool:
        """
        Check if text could be a prefix of a valid mask placeholder

        Args:
            text: Text to check

        Returns:
            True if text could be start of [MASK_XXX_N]
        """
        if not text.startswith('['):
            return False

        mask_template = "[MASK_"

        # Check if text is a prefix of mask template
        if len(text) <= len(mask_template):
            return mask_template.startswith(text)

        # Check if text matches full pattern partially
        if not text.startswith(mask_template):
            return False

        remainder = text[len(mask_template):]

        # Check if remainder matches partial pattern: LETTERS_DIGITS]
        for char in remainder:
            if not (char.isupper() or char == '_' or char.isdigit() or char == ']'):
                return False

        # If we haven't seen closing bracket yet, it's potentially incomplete
        if ']' not in remainder:
            return True

        # If closing bracket is present, check full pattern
        return bool(self.mask_pattern.match(text))


# ======================== Helper Functions ========================

def create_data_masker(config: dict) -> Optional[DataMasker]:
    """
    Factory function to create DataMasker from config

    Args:
        config: Full privacy_guard configuration

    Returns:
        DataMasker instance or None if disabled
    """
    data_masking_config = config.get('privacy_guard', {}).get('data_masking', {})

    if not data_masking_config.get('enabled', False):
        logger.info("[DataMasking] Data masking disabled in config")
        return None

    return DataMasker(data_masking_config)


# ======================== Testing Utility ========================

def test_masking():
    """Quick test function for data masking"""
    config = {
        'enabled': True,
        'rules': [
            {
                'name': 'Email',
                'pattern': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
                'entity_type': 'email'
            },
            {
                'name': 'Phone',
                'pattern': r'\b(?:\+?1[-.\\s]?)?\\(?[2-9]\\d{2}\\)?[-.\\s]?\\d{3}[-.\\s]?\\d{4}\b',
                'entity_type': 'phone'
            }
        ]
    }

    masker = DataMasker(config)

    # Test masking
    text = "Contact John at john.doe@example.com or call 123-456-7890"
    masked, store = masker.mask_prompt(text)
    print(f"Original: {text}")
    print(f"Masked: {masked}")

    # Test unmasking
    unmasked = masker.unmask_text(masked, store)
    print(f"Unmasked: {unmasked}")
    print(f"Match: {text == unmasked}")


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(level=logging.DEBUG)
    test_masking()
