"""自動把 pip 安裝的 NVIDIA CUDA DLL 目錄加入 DLL 搜尋路徑。

【坑4】ctranslate2 在 Windows 不會自動搜尋 pip 裝的 nvidia\\*\\bin。
缺 cublas64_12.dll 時，faster-whisper 不會報錯，而是「靜默 fallback 到 CPU」，
讓 large-v3 一句話從 ~0.3s 暴增到 ~6s，很容易誤以為是 GPU 太慢。

放在 venv 的 site-packages 下，該 venv 的 Python 每次啟動都會自動執行本檔。
注意：只 WhisperModel(...) 載入「不會」觸發缺 DLL，要 .transcribe() 跑 encode 才會，
所以驗證 GPU 一定要實際轉錄一次。
"""
import os

_base = os.path.join(os.path.dirname(__file__), "nvidia")
for _sub in ("cublas", "cudnn", "cuda_runtime", "cuda_nvrtc"):
    _p = os.path.join(_base, _sub, "bin")
    if os.path.isdir(_p):
        try:
            os.add_dll_directory(_p)
        except OSError:
            pass
        os.environ["PATH"] = _p + os.pathsep + os.environ.get("PATH", "")
