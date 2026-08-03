# Peptide workflow and provider disagreement — manuscript and rebuttal blocks

Date: 2026-08-04

Status: working draft. Results are frozen to the MDockPeP2 historical audit, ADCP formal
reference-redocking panel, ESMFold reference/prediction panels and AlphaFold 3 GLP1R-ECD panel.
Final section, table, page and line numbers remain `to verify`.

## AC-facing conclusion

The revised peptide branch separates sequence-to-complex prediction from peptide docking and
reports each provider against coordinate-grounded references; the available evidence supports
limited candidate prioritization and partial top-k interface recovery, with weak native-pose
ranking and substantial cross-provider pose disagreement retained explicitly.

## Revised workflow definition

| Stage | Manuscript-scope provider | Input | Output | Evaluation | Status and boundary |
|---|---|---|---|---|---|
| Candidate definition | FROGENT peptide workflow | Canonical peptide sequence and receptor construct | Versioned sequence/target pair | Sequence identity and construct audit | Noncanonical residue, lipid-spacer and terminal chemistry require explicit representation; omitted chemistry is outside the current panels |
| Sequence-to-complex prediction | ESMFold | GLP1R extracellular-domain sequence plus peptide sequence | Predicted receptor–peptide coordinates, pTM and pLDDT | Three public short-peptide reference complexes; cross-seed pose comparison | Supplementary structural signal; not a docking engine or experimental structure |
| Sequence-to-complex prediction | AlphaFold 3 | GLP1R extracellular-domain sequence plus one of eight peptide sequences | Predicted complex, pair-ipTM/ipTM and pLDDT | Semaglutide-to-4ZGM sequence-mapped coordinate/contact check; AF3–ESMFold pose comparison | Supplementary prioritization signal; only Semaglutide has a mapped coordinate reference in this panel |
| Peptide docking | ADCP 1.1.21 (`adcp` 0.0.25) | AGFR target prepared from 3GBQ, 1CKB or 1ABO plus peptide sequence | 100 ranked poses per task | Backbone/CA RMSD and native-contact recovery for 3 complexes × 3 seeds | Formal reference-redocking evidence; top-1 ranking is weak and top-k recovery is partial |
| Peptide docking | MDockPeP2 | Historical GLP1R/glucagon FASTA inputs and receptor setup | Ranked models and hybrid scores | Native-frame and superposed peptide CA RMSD | Historical negative audit only; a prospective isolated rerun requires an authorized Modeller runtime |
| Supplementary provider panel | TrioPep control-plane tasks | 3GBQ, 1CKB, 1ABO and exploratory 4ZGM definitions | Provider artifacts when terminal | Same reference metrics after artifact retrieval | Four tasks remain queued; they do not block or enter the current manuscript conclusions |

## Proposed Methods paragraph

The peptide workflow distinguishes candidate definition, sequence-to-complex prediction, peptide
docking and coordinate-grounded evaluation. ESMFold and AlphaFold 3 were treated as structure-
prediction comparators; ADCP and MDockPeP2 were treated as the peptide-docking methods. The formal
ADCP panel used receptor grids prepared from three deposited peptide–protein complexes (3GBQ,
1CKB and 1ABO), three seeds per complex, 100 replicas per task and 8–10 million sampling steps per
replica. Predictions were scored in the deposited-receptor coordinate frame using peptide
backbone/CA RMSD and native-contact recovery at 4.5 Å. The MDockPeP2 evidence was a read-only audit
of three historical glucagon runs; the historical inputs contained FASTA sequence files and no
separate experimentally derived secondary-structure constraint file was identified. ESMFold was
evaluated on 24 GLP1R-ECD candidate runs and nine runs across the three public reference
complexes. AlphaFold 3 was evaluated on eight GLP1R-ECD–peptide jobs; Semaglutide was the only
candidate with a sequence-mapped 4ZGM coordinate reference. All sequence-to-complex and docking
results were interpreted as computational prioritization signals.

## Proposed Results paragraph

ADCP completed all 9/9 formal reference-redocking tasks. Mean top-1/top-5/top-10 peptide backbone
RMSD was 11.262/5.840/4.690 Å, with corresponding native-contact recovery of
0.271/0.564/0.593, indicating weak native-pose ranking and partial top-k interface recovery. The
three historical MDockPeP2 glucagon runs contained 25,000 scores and 3,000 retained models; none
reached native-frame peptide CA RMSD ≤2 Å, and the best superposed value was 2.721 Å. ESMFold
completed 9/9 reference runs with mean peptide RMSD 6.526 Å; only 1/3 reference complexes reached
≤2 Å. AlphaFold 3 completed 8/8 GLP1R-ECD–peptide jobs with mean pair-ipTM 0.755. Its
sequence-mapped Semaglutide prediction had receptor-aligned peptide CA RMSD 8.133 Å and native-
contact recall/precision 0.882/0.732. AF3 and ESMFold peptide poses differed by 31.513 Å on
average, and their confidence rankings had Spearman rho -0.119. The provider disagreement and
mixed reference performance limit confidence scores to candidate prioritization; they do not
establish binding affinity or broad peptide-docking accuracy.

## Supplementary result table

| Provider | Formal denominator | Main structural result | Failure or disagreement retained | Usable claim |
|---|---:|---|---|---|
| ADCP | 3 complexes × 3 seeds; 100 poses/task | Top-1/top-5/top-10 RMSD 11.262/5.840/4.690 Å; contact recovery 0.271/0.564/0.593 | Native-pose ranking is weak; 29-residue glucagon use lies beyond the established ≤20-residue range | Partial top-k interface recovery on the three reference complexes |
| MDockPeP2 | 3 historical glucagon runs; 25,000 scores; 3,000 models | Best superposed CA RMSD 2.721 Å | No run reached native-frame CA RMSD ≤2 Å; prospective isolation lacks an authorized Modeller runtime | Historical audit does not support a near-native claim |
| ESMFold | 24 candidate runs; 9 reference runs | Reference mean RMSD 6.526 Å; 1/3 complexes ≤2 Å | 1ABO mean RMSD 15.914 Å; confidence is not affinity | Sequence-only comparative structure signal |
| AlphaFold 3 | 8/8 GLP1R-ECD–peptide jobs | Mean pair-ipTM 0.755; Semaglutide RMSD 8.133 Å; contact recall/precision 0.882/0.732 | Only Semaglutide has a mapped coordinate reference; noncanonical chemistry and full-length receptor omitted | Limited confidence/contact-based prioritization signal |
| AF3 versus ESMFold | 8 matched candidate sequences | Mean receptor-aligned peptide-pose difference 31.513 Å; confidence-rank rho -0.119 | Providers disagree strongly on pose and ranking | Disagreement must reduce confidence and motivate orthogonal validation |
| TrioPep | 4 submitted tasks | `not_measured` | All four remain queued; no artifacts available | Supplementary provider status only |

## Point-by-point response blocks

### R1-5a / how small-molecule and peptide conformations are generated

**Response.** We have separated the peptide branch into candidate definition, sequence-to-complex
prediction, peptide docking and structural evaluation. ESMFold and AlphaFold 3 provide
sequence-to-complex coordinates; ADCP and MDockPeP2 are the peptide-docking methods. The revised
Methods and Supplementary Table [to verify] will specify every provider, input construct, output,
sampling budget and evaluation metric. This prevents structure prediction, docking and confidence
scoring from being presented as interchangeable operations.

### R1-5b / glucagon secondary structure and validation

**Response.** The historical MDockPeP2 glucagon runs do not contain an independently documented
experimental secondary-structure constraint: the audited inputs contain FASTA sequences, and no
separate secondary-structure constraint file was identified. We will state this directly and
remove any implication that the submitted glucagon pose was experimentally constrained. The
coordinate-grounded validation now includes three public ADCP redocking complexes and three
public ESMFold reference complexes, together with the negative MDockPeP2 history.

### R1-9d / peptide capability and completion time

**Response.** The revised manuscript will report terminal task counts and structural accuracy
rather than treating a completed provider call as evidence of a correct pose. ADCP completed 9/9
formal tasks, ESMFold completed 24/24 candidate and 9/9 reference runs, and AlphaFold 3 completed
8/8 jobs. Provider-specific compute telemetry is retained where recorded; a matched end-to-end
wall-time comparison and private-provider queue time remain `not_measured`. The queued TrioPep
panel is supplementary and does not block the reported conclusions.

### R1-9e / MDockPeP2 and ADCP consistency

**Response.** We have aligned the manuscript with the providers that were actually verified.
ADCP is supported by a formal 3-complex × 3-seed reference-redocking panel. MDockPeP2 is supported
by a read-only historical audit whose negative pose results are reported; prospective performance
remains `not_measured` because the isolated runtime does not contain an authorized Modeller
license. HADDOCK and pepATTRACT will be removed from the capability description because no
production installation was verified.

## Required claim changes

- Retain: integrated peptide workflow, explicit provider routing, ADCP partial top-k interface
  recovery, negative MDockPeP2 historical audit and AF3/ESMFold prioritization signals.
- Narrow: all structure claims to the tested receptor constructs, sequences, references and
  chemistry representations.
- Remove: broad peptide-docking accuracy, binding-affinity prediction, full-length GLP1R,
  experimentally constrained glucagon secondary structure and unverified HADDOCK/pepATTRACT.
- `not_measured`: prospective MDockPeP2 accuracy, matched provider wall-time, private queue time,
  noncanonical Aib/lipid-spacer effects and TrioPep performance.

## Frozen evidence sources

- `runtime/evaluation/revision-20260731/gpu-final/mdockpep2/HISTORICAL_AUDIT.md`
- `runtime/evaluation/revision-20260731/gpu-final/mdockpep2/historical-audit-results.json`
- `/work/doomx/FROGENT/runtime/evaluation/revision-20260731/gpu-final/adcp-reference-formal-r01-score-r01/summary.json` (remote frozen evidence)
- `runtime/evaluation/revision-20260731/gpu-final/esmfold-glp1r/REFERENCE_REPORT.md`
- `runtime/evaluation/revision-20260731/gpu-final/esmfold-glp1r/analysis.json`
- `runtime/evaluation/revision-20260731/gpu-final/af3-glp1r/REPORT.md`
- `runtime/evaluation/revision-20260731/gpu-final/af3-glp1r/analysis.json`
- `runtime/evaluation/revision-20260730/nongpu-final/glp1r-peptide-audit/report.md`

