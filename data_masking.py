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
    Request-specific masking store
    Maintains bidirectional mapping between masked placeholders and original values
    """
    mask_to_original: Dict[str, str] = field(default_factory=dict)
    original_to_mask: Dict[str, str] = field(default_factory=dict)
    entity_counters: Dict[str, int] = field(default_factory=dict)

    def add_mapping(self, original: str, mask: str):
        """Add bidirectional mapping"""
        self.mask_to_original[mask] = original
        self.original_to_mask[original] = mask

    def get_original(self, mask: str) -> Optional[str]:
        """Get original value from mask"""
        return self.mask_to_original.get(mask)

    def get_mask(self, original: str) -> Optional[str]:
        """Get mask from original value"""
        return self.original_to_mask.get(original)

    def next_counter(self, entity_type: str) -> int:
        """Get next counter for entity type"""
        counter = self.entity_counters.get(entity_type, 0)
        self.entity_counters[entity_type] = counter + 1
        return counter


# ======================== DataMasker Core Class ========================

class DataMasker:
    """
    Core data masking engine with three-layer pipeline
    Layer 1: Built-in Regex -> Layer 2: Local SLM -> Layer 3: Custom Keywords
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
        Three-layer masking pipeline:
          1. Built-in Regex (email, phone, SSN, etc.)
          2. Local SLM Semantic Detection (optional)
          3. Custom Keywords (absolute confidential terms)

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

                # Check if already masked in store
                if original_value in store.original_to_mask:
                    # Reuse existing mask
                    mask_placeholder = store.get_mask(original_value)
                else:
                    # Generate new mask placeholder
                    counter = store.next_counter(rule.entity_type)
                    mask_placeholder = f"[MASK_{rule.entity_type.upper()}_{counter}]"

                    # Store mapping
                    store.add_mapping(original_value, mask_placeholder)

                # Replace in text
                start, end = match.span()
                masked_text = masked_text[:start] + mask_placeholder + masked_text[end:]

        # ============ Layer 2: Local SLM Semantic Detection ============
        if self.is_slm_available:
            try:
                sensitive_words = self._extract_sensitive_words_via_slm(masked_text)

                for word in sensitive_words:
                    if not word or len(word.strip()) == 0:
                        continue

                    # Check if already masked
                    if word in store.original_to_mask:
                        mask_placeholder = store.get_mask(word)
                    else:
                        # Generate SLM-specific mask
                        counter = store.next_counter('slm')
                        mask_placeholder = f"[MASK_SLM_{counter}]"
                        store.add_mapping(word, mask_placeholder)

                    # Replace all occurrences
                    masked_text = masked_text.replace(word, mask_placeholder)

            except Exception as e:
                logger.warning(f"[DataMasker] Layer 2 (SLM) failed, continuing: {e}")

        # ============ Layer 3: Custom Keywords ============
        for keyword in self.custom_keywords:
            if not keyword:
                continue

            # Check if already masked
            if keyword in store.original_to_mask:
                mask_placeholder = store.get_mask(keyword)
            else:
                # Generate keyword-specific mask
                counter = store.next_counter('keyword')
                mask_placeholder = f"[MASK_KEYWORD_{counter}]"
                store.add_mapping(keyword, mask_placeholder)

            # Case-insensitive replacement
            masked_text = re.sub(
                re.escape(keyword),
                mask_placeholder,
                masked_text,
                flags=re.IGNORECASE
            )

        logger.debug(f"[DataMasker] Masked {len(store.mask_to_original)} entities "
                    f"(Regex: {len([k for k in store.entity_counters if k not in ['slm', 'keyword']])}, "
                    f"SLM: {store.entity_counters.get('slm', 0)}, "
                    f"Keywords: {store.entity_counters.get('keyword', 0)})")
        return masked_text, store

    def unmask_text(self, text: str, store: MaskingStore) -> str:
        """
        Unmask text using masking store (non-streaming)

        Args:
            text: Masked text
            store: Masking store from mask_prompt

        Returns:
            Unmasked text with original values restored
        """
        if not self.enabled or not store.mask_to_original:
            return text

        unmasked_text = text

        # Replace all mask placeholders with original values
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
    Streaming unmasker with sliding window buffer
    Handles chunked streaming responses where mask placeholders may be split across chunks
    """

    def __init__(self, store: MaskingStore):
        """
        Initialize StreamUnmasker

        Args:
            store: Masking store from mask_prompt
        """
        self.store = store
        self.buffer = ""
        self.mask_pattern = re.compile(r'\[MASK_[A-Z_]+_\d+\]')

    async def unmask_stream(self, chunk_iterator: AsyncIterator[str]) -> AsyncIterator[str]:
        """
        Unmask streaming chunks with sliding window buffer

        Args:
            chunk_iterator: Async iterator of text chunks from upstream LLM

        Yields:
            Unmasked text chunks
        """
        async for chunk in chunk_iterator:
            # Add chunk to buffer
            self.buffer += chunk

            # Try to extract and unmask complete tokens
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
                    # Valid mask starts: [M, [MA, [MAS, [MASK, [MASK_, etc.
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

        # Valid prefix patterns: [, [M, [MA, [MAS, [MASK, [MASK_, [MASK_E, etc.
        mask_template = "[MASK_"

        # Check if text is a prefix of mask template
        if len(text) <= len(mask_template):
            return mask_template.startswith(text)

        # Check if text matches full pattern partially
        # Pattern: [MASK_XXXX_N]
        # After [MASK_, we expect uppercase letters, _, digits, ]
        if not text.startswith(mask_template):
            return False

        remainder = text[len(mask_template):]

        # Check if remainder matches partial pattern: LETTERS_DIGITS]
        # Allow: uppercase letters, underscore, digits, closing bracket
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
