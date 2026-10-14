# Dataset

This project uses documents and questions from [LegalBench-RAG](https://github.com/zeroentropy-ai/legalbenchrag). The data is not included in this repository. Download it from the LegalBench-RAG repository and check the usage terms of LegalBench-RAG and its source datasets (ContractNLI, CUAD, MAUD and PrivacyQA) before use.

## Folder layout

Place the downloaded `corpus` and `benchmarks` folders under `data/rag_legal/`:

```text
data/
  README.md
  rag_legal/
    corpus/
      contractnli/
      cuad/
      maud/
      privacy_qa/
    benchmarks/
      contractnli.json
      cuad.json
      maud.json
```

The notebook reads these files directly. Everything under `data/` except this README is ignored by Git.

## Data used for the saved results

The saved results use a subset of LegalBench-RAG with the following files:

| Collection | Documents | Benchmark questions | Questions with source documents |
|---|---:|---:|---:|
| ContractNLI | 93 | 977 | 962 |
| CUAD | 431 | 4,042 | 3,753 |
| MAUD | 117 | 1,676 | 1,318 |
| PrivacyQA | 3 | Not used | Not evaluated |
| **Total** | **644** | **6,695** | **6,033** |

- The three benchmark files reference 66 documents that are not in this subset. The notebook loads all 6,695 questions and evaluates only the 6,033 whose source documents are available.
- Each benchmark answer is a supporting text span, given as a file path and character range.
- File paths are normalised to the same Unicode form, and line endings are normalised on load.
- The full LegalBench-RAG download contains more documents and a PrivacyQA benchmark, so counts from a full download will differ.

Running the notebook sends document text and questions to OpenAI for embeddings, answer generation and evaluation.
