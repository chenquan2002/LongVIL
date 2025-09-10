# LongVIL: Long-Horizon Visual Imitation Learning via Plan and Code Reflection

Official implementation of the paper:  
[**Long-Horizon Visual Imitation Learning via Plan and Code Reflection**](https://arxiv.org/abs/2509.05368)  

📂 Dataset: [LongVILBench](https://huggingface.co/datasets/cq838/LongVILBench)  

---

## 🔧 Environment Setup
Our experiments were conducted on:
- Ubuntu 22.04.4 LTS  
- Python 3.10.14  
- PyTorch 2.4.0+cu121  
- NVIDIA 4090D GPU  

Create the environment from the provided `environment.yml`:
```bash
conda env create -f environment.yml -n longvil
conda activate longvil
```

---

## 🎯 Keyframe Extraction (based on SeeDo)
We adopt and extend the **keyframe extraction** module from [SeeDo](https://github.com/ai4ce/SeeDo).  
This step **must be done before running the benchmark**.

- Original SeeDo extracts keyframes for either left **or** right hand.  
- Our improved version allows extracting keyframes for **both hands independently**.  

We provide a modified script (`get_frames.py`):  
1. Install GroundingDINO, SAM, and SAM2 as in SeeDo.  
2. Replace the original SeeDo script (`get_frame_by_hands.py`) with ours (`get_frames.py`).  
3. For detailed setup instructions, see [docs/keyframe_extraction.md](docs/keyframe_extraction.md).  

---

## 📂 Dataset Preparation
Download [LongVILBench](https://huggingface.co/datasets/cq838/LongVILBench).  

Place the dataset under:
```
LongVIL/data
├── level1/
├── level2/
└── level3/
```
⚠️ The downloaded dataset (`level1, level2 and level3`) should **replace the `example` folder** inside `LongVIL/data/`.  

---

## 🚀 Usage

### Training & Inference
Run:
```bash
bash run.sh
```
⚠️ Edit `run.sh` to add your API key and specify the benchmark level.

---

## 📊 Evaluation

Run:
```bash
python evaluate.py
```
Edit the following lines in `evaluate.py` according to the target level:
```python
OUTPUT_ROOT = Path("./output/data/level2")
GT_ROOT     = Path("./data/level2")
```

### Metrics
We provide three metrics:
1. **Exact Match Accuracy (EMA)** – sequence match  
2. **Step-wise Matching Score (SMS)** – prefix match  
3. **Final State Accuracy (FSA)** – final state correctness  

> EMA is computed via `evaluate.py`; SMS and FSA require manual/video evaluation.  

---

## 📖 Citation
If you use this work, please cite:

```bibtex
@misc{chen2025longhorizonvisualimitationlearning,
  title        = {Long-Horizon Visual Imitation Learning via Plan and Code Reflection},
  author       = {Quan Chen and Chenrui Shi and Qi Chen and Yuwei Wu and Zhi Gao and Xintong Zhang and Rui Gao and Kun Wu and Yunde Jia},
  year         = {2025},
  eprint       = {2509.05368},
  archivePrefix= {arXiv},
  primaryClass = {cs.RO},
  url          = {https://arxiv.org/abs/2509.05368}
}
```

---

## 📜 License
This project is released under the **Apache-2.0 License**.  
