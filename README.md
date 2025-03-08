# PixelPiper


NOTE: (this is a draft)

**PixelPiper** is a modular and extensible image processing pipeline framework built in Python. It enables users to define and execute image processing steps asynchronously, with built-in support for retries, timeouts, and context management.

## Features

- **Pipeline-based execution**: Define and run sequences of image processing steps.
- **Asynchronous processing**: Steps are executed asynchronously using `asyncio` for efficient performance.
- **Decorators for step metadata**: Use `@step`, `@requires`, `@provides`, `@timeout`, and `@max_retries` to define steps with clear dependencies and constraints.
- **Callback system**: Implement custom callbacks for logging, timing, and monitoring execution.
- **Automatic retry and timeout handling**: Ensure robustness by configuring retry attempts and execution time limits.

---

## Installation

You can install PixelPiper using `pip`:

```sh
pip install pixelpiper
```

(Replace with the actual package name if published on PyPI.)

---

## Usage

### Defining a Pipeline Step

Steps in PixelPiper are created by subclassing `PipelineStep` and using decorators to define their metadata:

```python
from PIL import Image
from typing import Dict, Any
from pixelpiper.pipeline import PipelineStep, StepResult, StepStatus
from pixelpiper.decorators import step, requires, provides, timeout, max_retries

class ImageResizeStep(PipelineStep):
    """Resizes an image based on the target size."""
    
    @step(name="image_resize")
    @requires("input_size")
    @provides("resized_image", "resize_factor")
    @timeout(10.0)
    @max_retries(2)
    async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult:
        try:
            target_size = context["input_size"]
            width, height = image.size
            resize_factor = target_size / max(width, height)
            new_size = (int(width * resize_factor), int(height * resize_factor))
            resized_image = image.resize(new_size)
            
            return StepResult(
                status=StepStatus.COMPLETED,
                data={"resized_image": resized_image, "resize_factor": resize_factor}
            )
        except Exception as e:
            return StepResult(status=StepStatus.FAILED, data={}, error=str(e))
```

---

### Running a Pipeline

A pipeline consists of multiple processing steps, executed in sequence:

```python
import asyncio
from PIL import Image
from pixelpiper.pipeline import Pipeline, PipelineConfig
from pixelpiper.callbacks import TimingCallback
from examples.image_steps import ImageResizeStep

async def main():
    config = PipelineConfig(max_retries=3, timeout=15.0)
    pipeline = Pipeline(config, callbacks=[TimingCallback()])

    # Add processing steps
    pipeline.add_step(ImageResizeStep())

    # Create a sample image
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
```

---

## API Reference

### `PipelineStep`
Base class for all steps in the pipeline.

- `name`: Name of the step.
- `required_context_keys`: List of required keys in the context.
- `provided_context_keys`: List of keys this step adds to the context.

#### `async def process(self, image: Image.Image, context: Dict[str, Any]) -> StepResult`
The core method that processes the image and updates the pipeline context.

---

### Decorators

- `@step(name)`: Assigns a custom name to a step.
- `@requires(*keys)`: Specifies required context keys.
- `@provides(*keys)`: Declares what keys this step will add to the context.
- `@timeout(seconds)`: Sets a timeout for the step execution.
- `@max_retries(count)`: Defines how many times the step should retry on failure.

---

### `Pipeline`
Orchestrates and executes the pipeline steps.

- `Pipeline(config, callbacks)`: Initializes a pipeline.
- `add_step(step)`: Adds a step to the pipeline.
- `add_callback(callback)`: Adds a callback to monitor execution.
- `async def run(image, initial_context)`: Runs the pipeline with an image and context.

---

### `StepResult`
The result of a pipeline step.

- `status`: `StepStatus` enum (`COMPLETED`, `FAILED`, etc.).
- `data`: Dictionary with output values.
- `error`: Optional error message if the step fails.

---

## Contributing

We welcome contributions! Please follow these steps:

1. Fork the repository.
2. Create a feature branch (`git checkout -b feature-branch`).
3. Commit your changes (`git commit -m "Add new feature"`).
4. Push to the branch (`git push origin feature-branch`).
5. Open a pull request.

---

## License

This project is licensed under the Apache 2.0 License. See [LICENSE](LICENSE) for details.

---

## Acknowledgments

This project was inspired by modular processing frameworks and designed for AI-driven image processing workflows.
