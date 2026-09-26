"use client";

import { useState, useRef } from "react";

export function useAudioReactive() {
  const [isListening, setIsListening] = useState(false);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const dataArrayRef = useRef<Uint8Array | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

  const startListening = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)();
      analyserRef.current = audioContextRef.current.createAnalyser();
      analyserRef.current.fftSize = 256;
      sourceRef.current = audioContextRef.current.createMediaStreamSource(stream);
      sourceRef.current.connect(analyserRef.current);
      
      const bufferLength = analyserRef.current.frequencyBinCount;
      dataArrayRef.current = new Uint8Array(bufferLength);
      
      setIsListening(true);
    } catch (err) {
      console.error("Microphone access denied", err);
    }
  };

  const stopListening = () => {
    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }
    setIsListening(false);
  };

  // Get the current average frequency (0 to 255)
  const getAudioLevel = () => {
    if (!analyserRef.current || !dataArrayRef.current) return 0;
    analyserRef.current.getByteFrequencyData(dataArrayRef.current as any);
    
    let sum = 0;
    for (let i = 0; i < dataArrayRef.current.length; i++) {
      sum += dataArrayRef.current[i];
    }
    return sum / dataArrayRef.current.length;
  };

  return { isListening, startListening, stopListening, getAudioLevel };
}

