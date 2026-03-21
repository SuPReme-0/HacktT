import torch
from PIL import Image
import gc
from transformers import AutoProcessor, AutoModelForCausalLM
from utils.memory import vram_guard
from utils.logger import get_logger

logger = get_logger("hackt.core.vision")

class VisionEngine:
    def __init__(self, model_id: str = "microsoft/Florence-2-base"):
        self.model_id = model_id
        self.model = None
        self.processor = None
        # VRAM Footprint in FP16 is roughly ~750MB
        self.required_vram_gb = 0.8 

    def _load(self) -> bool:
        """Loads Florence-2 into VRAM using extreme optimization flags."""
        if self.model is not None:
            return True

        if not vram_guard.can_load_model(self.required_vram_gb):
            logger.warning("Vision Engine: Insufficient VRAM to load Florence-2.")
            return False

        logger.info("Vision Engine: Mounting Florence-2 to GPU in FP16...")
        try:
            # OPTIMIZATION 1 & 2: FP16 precision and SDPA (Flash Attention)
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_id, 
                trust_remote_code=True,
                torch_dtype=torch.float16,
                attn_implementation="sdpa" 
            ).to("cuda")

            self.processor = AutoProcessor.from_pretrained(
                self.model_id, 
                trust_remote_code=True
            )
            return True
        except Exception as e:
            logger.error(f"Vision Engine: Failed to mount Florence-2: {e}")
            self._unload()
            return False

    def _unload(self):
        """Nuclear VRAM wipe. Purges the model completely from memory."""
        if self.model is not None:
            logger.info("Vision Engine: Unmounting Florence-2...")
            del self.model
            del self.processor
            self.model = None
            self.processor = None
            
            # Force Python garbage collection, then force PyTorch cache clear
            gc.collect()
            vram_guard.clear_cuda_cache()

    def analyze_screen(self, image: Image.Image, task_prompt: str = "<OCR>") -> str:
        """
        The Ephemeral Execution Loop.
        Loads -> Scans -> Unloads -> Returns Result.
        """
        # 1. Mount
        if not self._load():
            return "[SYSTEM_ERROR: VRAM Starvation]"

        try:
            # 2. Process Image (Ensure RGB format for Florence)
            if image.mode != "RGB":
                image = image.convert("RGB")

            inputs = self.processor(
                text=task_prompt, 
                images=image, 
                return_tensors="pt"
            ).to("cuda", torch.float16)

            # 3. Inference
            generated_ids = self.model.generate(
                input_ids=inputs["input_ids"],
                pixel_values=inputs["pixel_values"],
                max_new_tokens=512,
                num_beams=3, # Low beam search for speed
                do_sample=False
            )

            # 4. Decode
            generated_text = self.processor.batch_decode(
                generated_ids, 
                skip_special_tokens=False
            )[0]
            
            parsed_answer = self.processor.post_process_generation(
                generated_text, 
                task=task_prompt, 
                image_size=(image.width, image.height)
            )

            result = parsed_answer.get(task_prompt, "")
            
            # If the OCR result is a list of strings, join them
            if isinstance(result, list):
                result = "\n".join(result)
                
            return result

        except Exception as e:
            logger.error(f"Vision Engine: Analysis failed: {e}")
            return f"[SYSTEM_ERROR: {str(e)}]"

        finally:
            # 5. Guaranteed Unmount (Even if inference crashes)
            self._unload()

vision_engine = VisionEngine()