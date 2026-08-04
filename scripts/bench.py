import time
import numpy as np
from faster_whisper import WhisperModel

# 5 秒測試音訊（白噪音；計算量與真實語音同等級，用來量管線速度）
fs = 16000
audio = (np.random.randn(5 * fs) * 0.05).astype(np.float32)

def bench(model_name, beam, lang):
    m = WhisperModel(model_name, device="cuda", compute_type="float16")
    # warmup（第一次含 CUDA kernel 編譯/cuDNN autotune）
    list(m.transcribe(audio, beam_size=beam, language=lang)[0])
    # 真正計時（取 3 次平均）
    ts = []
    for _ in range(3):
        t = time.perf_counter()
        list(m.transcribe(audio, beam_size=beam, language=lang, vad_filter=False)[0])
        ts.append(time.perf_counter() - t)
    print(f"{model_name:18s} beam={beam} lang={lang or 'auto':4s} -> {sum(ts)/len(ts)*1000:6.0f} ms/句")

for name in ["large-v3", "large-v3-turbo"]:
    for beam in (5, 1):
        bench(name, beam, "zh")
