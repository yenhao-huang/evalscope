# Environment rules

- Python >=3.10 upstream; use Python 3.11 for this experiment. Create the environment at repository root `.venv` using `uv venv --python 3.11 .venv`; install with `uv pip install --python .venv/bin/python -e .`.
- Read this file before installing dependencies or starting services. Use `.venv/bin/python` and `.venv/bin/pytest`; never install this fork into another project environment.
- Upstream dependencies: `requirements/framework.txt` and `pyproject.toml`. Record resolved package versions in the experiment after installation.
- Sources: `~/Desktop/datasets/full-textgen-evalset`, `~/Desktop/datasets/vision-dataset`, and `~/Desktop/datasets/chinese-question-eval/converted/opseval`. Override via converter arguments on another machine.
- Local model: `~/Desktop/models/gemma-4-26B-A4B-it-GGUF/gemma-4-26B-A4B-it-UD-Q4_K_XL.gguf`; mmproj: sibling `mmproj-BF16.gguf`. Existing launch script uses `llama-server`, port 8092, context 8192, temperature 0.
- Remote target: DGX Spark `100.109.182.22`, requested config `gemma-4-26B-A4B-it.yaml`. SSH username, config path, backend, endpoint and quantization must be discovered; do not assume parity with local GGUF.
- Keep API keys in environment variables; do not write them to tracked configs or reports.
- Validate converters/scorers with offline tests, then a live smoke run before full evaluation. Infrastructure failures are failures, never successful scores. Record prompt, sampling, model identity, dataset hashes, sample counts, runtime, and scoring version.
- Never execute model-generated shell commands on the host. HumanEval must use isolated code execution with time and resource limits.
