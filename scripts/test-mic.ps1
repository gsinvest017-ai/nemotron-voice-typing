# 麥克風收音測試：倒數後錄 4 秒，印出音量強度，確認硬體層有收到聲音。
$ErrorActionPreference = 'Stop'
$py = "$PSScriptRoot\.venv\Scripts\python.exe"
& $py -c @"
import sounddevice as sd, numpy as np, time
dev = sd.query_devices(kind='input')
print('使用裝置:', dev['name'])
for i in (3,2,1):
    print(f'  {i}...'); time.sleep(1)
print('>>> 現在開始講話！(錄 4 秒) <<<')
fs = 16000
rec = sd.rec(int(4*fs), samplerate=fs, channels=1, dtype='float32'); sd.wait()
peak = float(np.abs(rec).max()); rms = float(np.sqrt((rec**2).mean()))
print(f'峰值={peak:.4f}  RMS={rms:.4f}')
if peak < 0.01:   print('結果: 幾乎沒收到聲音 -> 麥克風靜音/音量0/裝置錯誤')
elif peak > 0.95: print('結果: 爆音(削峰) -> Windows 輸入音量調低一點')
else:             print('結果: 收音正常')
"@
