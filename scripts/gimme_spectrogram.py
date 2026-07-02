import matplotlib.pyplot as plt
from scipy.io import wavfile


sample_rate, audio = wavfile.read("assets/gimme.wav")
plt.specgram(audio, Fs=sample_rate)
plt.xlabel("Time (seconds)")
plt.ylabel("Frequency (Hz)")
plt.savefig("gimme_spectrogram.png")
