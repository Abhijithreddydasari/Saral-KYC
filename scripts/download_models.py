import os
import subprocess
import sys
import urllib.request
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "app" / "models_data"
VISION_DIR = MODELS_DIR / "vision"
FORGERY_DIR = MODELS_DIR / "forgery"

def download_donut():
    logger.info("Downloading Donut DocVQA model...")
    VISION_DIR.mkdir(parents=True, exist_ok=True)
    
    try:
        from transformers import DonutProcessor, VisionEncoderDecoderModel
        
        model_name = "nielsr/donut-base-finetuned-docvqa"
        logger.info(f"Fetching {model_name} from Hugging Face Hub...")
        
        processor = DonutProcessor.from_pretrained(model_name)
        model = VisionEncoderDecoderModel.from_pretrained(model_name)
        
        save_path = VISION_DIR / "donut-docvqa"
        processor.save_pretrained(save_path)
        model.save_pretrained(save_path)
        logger.info(f"Donut model saved to {save_path}")
        
    except ImportError:
        logger.error("transformers library not found. Please install it first.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Failed to download Donut model: {e}")
        sys.exit(1)

def download_spacy():
    logger.info("Downloading SpaCy model (en_core_web_md)...")
    try:
        subprocess.check_call([sys.executable, "-m", "spacy", "download", "en_core_web_md"])
        logger.info("SpaCy model downloaded successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to download SpaCy model: {e}")
        sys.exit(1)

def download_minifasnet():
    logger.info("Downloading MiniFASNetV2 PyTorch model...")
    FORGERY_DIR.mkdir(parents=True, exist_ok=True)
    
    # Direct raw link to the .pth file in the repo
    url = "https://github.com/minivision-ai/Silent-Face-Anti-Spoofing/raw/master/resources/anti_spoof_models/2.7_80x80_MiniFASNetV2.pth"
    
    target_path = FORGERY_DIR / "2.7_80x80_MiniFASNetV2.pth"
    
    if target_path.exists():
        logger.info("MiniFASNetV2.pth already exists. Skipping.")
        return

    try:
        logger.info(f"Downloading from {url}...")
        # Use a custom User-Agent to avoid 403/404 from GitHub if simple script
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req) as response, open(target_path, 'wb') as out_file:
            data = response.read()
            out_file.write(data)
            
        logger.info(f"Saved to {target_path}")
    except Exception as e:
        logger.warning(f"Could not download MiniFASNetV2.pth automatically: {e}")
        logger.warning("Please manually place '2.7_80x80_MiniFASNetV2.pth' in app/models_data/forgery/")

def main():
    logger.info("Starting model downloads...")
    # Donut and SpaCy are likely already done, but the script checks existence/installation
    download_donut()
    download_spacy()
    download_minifasnet()
    logger.info("All model downloads completed.")

if __name__ == "__main__":
    main()
