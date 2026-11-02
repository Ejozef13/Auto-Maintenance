# AI Garage setup

The AI Garage button is available after opening a car. The desktop application
connects to separately running Ollama, ComfyUI, and optionally SearXNG services.
It does not install those services or download models automatically.

## 1. Start chat locally

Install Ollama for your OS and confirm that it supports GPU acceleration for your
AMD RX 9070 XT with your driver/runtime combination. GPU compatibility is separate
from the Python app; verify it with `ollama ps` while a request is running.

A 7–8B instruction model is the initial recommendation for 16 GB VRAM:

```bash
ollama pull qwen2.5:7b
ollama serve
```

If Ollama is already running as a service, do not start another server.
Use any installed model's exact tag in AI settings. If your 20B model is
`gpt-oss:20b`, that tag can be used instead; confirm the name using `ollama list`.
Compare actual response time and evidence accuracy before choosing a default.
Quantization, context size, and runtime overhead affect memory and speed.
Do not assume chat and image generation will both fit in VRAM simultaneously.
If necessary, stop loaded chat models with `ollama stop <model-tag>` before
portrait generation; the next chat request loads the model again.

Run the app, open a car, choose **AI Garage → AI settings**, and use
**Test Ollama / list models**. Defaults point to `http://127.0.0.1:11434`.
Save your preferred model tag, then ask a general car question.

## 2. Import the matching owner's manual

TXT/Markdown import works with Python's standard library. For PDF support:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements-ai.txt
python3 main.py
```

Choose **Import manual** in the assistant tab. Match the manual to the car's
year, model, market, engine, and trim; the app cannot verify the document's identity.
Text is stored locally in `ai_data/manuals.sqlite3`, scoped to that car's ID.
Original files remain untouched. Reimporting a filename replaces its existing
passages for that car. Import multiple differently named manuals if needed.
Scanned PDFs require OCR outside the app first; there is no OCR pipeline yet.

Ask a concrete question such as “What oil viscosity does my manual specify?”
Answers are prompted to cite `[M1]` style references. Retrieved excerpts appear
underneath each answer with the source filename and **PDF page position**, which
may differ from the page number printed on the document. Read the excerpts to
verify the claim; citations are not a guarantee that a model interpreted them correctly.

Retrieval currently uses SQLite FTS5/BM25 lexical ranking with overlapping
360-word passages. This is retrieval-augmented generation (RAG), not fine-tuning.
It is lightweight and works offline without an embedding service. Synonyms and
complex follow-ups can miss relevant passages. A dedicated embedding model plus
hybrid search/reranking is the next useful upgrade if an evaluation shows misses;
a larger chat model alone does not fix missing evidence.

Chat includes the car's name, notes, odometer, and up to 30 most recent service
records. Follow-up messages are retained only for the open window, with bounded
context. The assistant cannot modify records or run commands. Specific capacities,
procedures, schedules, and torque values are instructed to require matching manual
evidence; generated answers still require verification.

## 3. Generate portraits through ComfyUI

Install ComfyUI using instructions appropriate to your AMD GPU and OS. Start its
server (default `http://127.0.0.1:8188`) and test image generation in ComfyUI first.
Select a model/checkpoint you have permission to use and enough memory to run.

The included `examples/comfyui-sdxl-api.json` is a standard SDXL text-to-image
example. Change its `ckpt_name` to your installed compatible SDXL checkpoint's
exact filename. It does not download a checkpoint. Model-specific workflows,
such as those for other image-model families, require their own nodes and settings.

Alternatively, export your tested ComfyUI workflow **in API format**. Use
`{{PROMPT}}` in the positive text prompt and include a **SaveImage** output.
Regular workflow JSON containing a `nodes` array is not API format.

In AI settings, import the API JSON. In **Garage portrait**, enter appearance
information, update/edit the prompt, and choose **Generate portrait**. The app queues
the workflow, polls its job history, downloads the resulting PNG, and saves it per
car. Saved portraits replace the drawing on garage cards when you return to
**My garage**. PNGs and prompt metadata stay in `ai_data/`.

This is an illustrative 2D portrait with a 3D render style, not a rotatable mesh or
an exact vehicle identification. Prompting uses the car name and appearance only,
not VIN, notes, or service history. Closing the AI window stops waiting but does
not cancel a job already running in ComfyUI. Check its queue before retrying if a
job times out. Previous portraits remain when generation fails.

## 4. Optional internet evidence

Run or select a SearXNG instance with JSON search enabled in its settings:

```yaml
search:
  formats:
    - html
    - json
```

Save its base URL in AI settings. Turn on **Search the web for this question**
only for questions where you want external lookup. The checkbox is off by default.
The car name and current question are sent to SearXNG and its search providers;
manual text, notes, and service history are not included in that search query.

Up to four search snippets and their URLs are included as `[W1]` style sources.
This version searches snippets; it does not crawl complete pages or autonomously
browse. Snippets can be stale or describe a different car. The assistant is
instructed to prefer the matching manual and disclose conflicts. Search failures
are shown explicitly and the assistant can still answer from available local data.

## Data, verification, and limitations

AI data is separate from `garage_data.json` and ignored by Git. Chat goes to the
configured Ollama server; portraits go to the configured ComfyUI server. Keep
these services local or use trusted protected servers. There is no authentication
configuration for remote services in this version. Deleting a garage car does not
erase its AI cache; use Remove manuals first, or remove its cached assets manually.
Back up `ai_data/` separately if you want to retain imported text and portraits.

Run automated checks with `python3 -m unittest discover -s tests -v`.
Offline tests cover car isolation, page references, reimport behavior, settings,
retrieval context, web privacy/failure handling, and ComfyUI workflow/job handling.
Tests mock external AI services; they do not establish live answer quality or GPU
compatibility. GUI tests need a display.

For a resume demo, evaluate a small set of questions with expected manual pages:
measure passage recall, citation correctness, unsupported claims, and response
latency with both your 7B and 20B models. Include no-answer questions and an
incorrect-model-year manual. Report measured results rather than claiming that
RAG or web search automatically guarantees accuracy.
