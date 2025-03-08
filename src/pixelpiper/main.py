# main.py
import asyncio
from PIL import Image
from pixelpiper.pipeline import Pipeline, PipelineConfig
from pixelpiper.callbacks import TimingCallback
from pixelpiper.image_steps import ImageResizeStep

async def main() -> None:
    config = PipelineConfig(max_retries=3, timeout=15.0, ui_url="http://localhost:3000")
    pipeline = Pipeline(config, callbacks=[TimingCallback()])
    pipeline.add_step(ImageResizeStep())
    image = Image.new("RGB", (800, 600), color="white")
    context = {"input_size": 400}
    try:
        result = await pipeline.run(image, context)
        print("Pipeline completed successfully!")
        print("Results:", result)
    except Exception as e:
        print("Pipeline failed:", e)

if __name__ == "__main__":
    asyncio.run(main())
