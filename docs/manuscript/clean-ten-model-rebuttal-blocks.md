# Clean ten-model comparison: manuscript and rebuttal blocks

## Suggested point-by-point response

We thank the reviewer for requesting a comparison against stronger current models. We therefore
ran a new clean comparison covering ten models and the same eight author-supplied task families:
GPT-5.4, GPT-5.5, GPT-5.6 Sol, DeepSeek V4 Flash, DeepSeek V4 Pro, Kimi K2.5, Qwen3.7 Plus,
GLM 5.2, MiniMax M3 and MiMo V2.5. Each task contained 20 exposed cases. Every execution excluded
the FROGENT system prompt and initialization, previous conversation state, persistent memory, web
access and tools; reference answers were withheld until deterministic scoring. All 80 model–task
cells completed.

The results show substantial task specificity. The descriptive across-task macro means were
0.449 for GPT-5.5, 0.445 for GPT-5.6 Sol and 0.405 for MiniMax M3, with broadly overlapping
task-bootstrap intervals. The highest individual task scores were distributed across five model
families: MiniMax M3 for foundational knowledge and binding-mechanism counts, DeepSeek V4 Pro for
known-drug retrieval, MiMo V2.5 for known-target retrieval, GPT-5.6 Sol for property prediction
and virtual screening, and Qwen3.7 Plus for molecular design; GPT-5.6 Sol and DeepSeek V4 Flash
tied on the exact-reference retrosynthesis score. We added the full 10×8 heatmap and sample-level
outputs. Because the eight task scores have different meanings and the intervals overlap, we use
the macro mean as a descriptive summary and do not claim a statistically supported universal
model ranking. This clean panel also does not measure the added contribution of FROGENT
orchestration, retrieval, memory or tool use.

## Suggested Methods insertion

### Clean current-model comparison

We evaluated ten current language models on eight author-supplied exposed task sets containing
20 cases each. GPT-5.4, GPT-5.5 and GPT-5.6 Sol were executed through the bundled Codex client in
ephemeral isolated repositories with project instructions disabled, read-only sandboxing and web
search disabled. The seven non-OpenAI models were called by pinned OpenRouter model identifiers
with provider fallback disabled. All calls received only the task instruction, case inputs and a
strict output schema; FROGENT initialization, previous turns, persistent memory, tools, web access
and reference answers were excluded. Gold answers were loaded only by the deterministic scorer
after inference. Compatibility amendments changed only reasoning exposure, request grain or the
exact provider route for the same model. Oversized cells were divided into four stateless
five-case calls while preserving case-level scoring. Initial failures and recovery provenance
were retained.

Primary scores were normalized to [0,1] separately by task: exact accuracy for foundational
knowledge; DrugBank-ID recall@5 for known-drug retrieval; exact-set F1 for known-target retrieval;
the mean of endpoint-specific property scores; exact selected-ligand accuracy over 19 valid
virtual-screening cases; exact interaction-field accuracy; the mean of molecule validity,
within-case uniqueness, QED and normalized synthetic-accessibility easiness; and the mean of
target-rooted route validity and exact-reference reaction recall for retrosynthesis. The
across-task macro mean is descriptive because these task metrics represent different scientific
constructs. Uncertainty was estimated by resampling the eight task scores with replacement.

## Suggested Results insertion

All 80 model–task cells completed and were scored. GPT-5.5 and GPT-5.6 Sol had the highest
descriptive macro means (0.449 and 0.445), followed by MiniMax M3 (0.405); their task-bootstrap
95% intervals were [0.303,0.619], [0.280,0.632] and [0.229,0.608], respectively, and overlapped
substantially. No model led every task. MiniMax M3 led foundational knowledge (0.450) and
binding-mechanism counts (0.400); DeepSeek V4 Pro led known-drug retrieval (0.643); MiMo V2.5 led
known-target retrieval (0.340); GPT-5.6 Sol led property prediction (0.766) and virtual screening
(0.421); Qwen3.7 Plus led molecular design (0.950); and GPT-5.6 Sol and DeepSeek V4 Flash tied on
retrosynthesis (0.500). These results support task-dependent model selection and provide a
current no-tool baseline. They do not quantify a FROGENT orchestration advantage.

## Suggested figure caption

**Figure X | Clean comparison of ten current models across eight exposed benchmark tasks.**
Each heatmap cell is the normalized score over 20 author-supplied cases, except virtual screening,
which excludes one source case whose exact gold ligand is absent from its candidate set. Gold
answers were withheld during inference. Models received no FROGENT initialization, previous
history, persistent memory, web access or tools. The right panel shows the descriptive unweighted
macro mean and a 95% interval obtained by resampling task scores. The eight task metrics differ in
scientific meaning; macro means and intervals are therefore summaries of this panel rather than
a universal model ranking. Complete prompts, outputs, failures, compatibility amendments and
scorer files are retained in the accompanying evaluation package.
