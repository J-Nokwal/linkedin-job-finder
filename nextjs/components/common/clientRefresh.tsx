"use client";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

export default function AutoRefresh({ intervalSec = 5 }) {
  const [pct, setPct] = useState(100);
  const searchParams = useSearchParams();
  const enabled = searchParams.has("autoRefresh");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const ms = intervalSec * 1000;

    function start() {
      const begin = Date.now();

      intervalRef.current = setInterval(() => {
        setPct(100 * (1 - (Date.now() - begin) / ms));
      }, 100);

      timeoutRef.current = setTimeout(() => {
        clearInterval(intervalRef.current!);
        window.location.reload(); // 👈 guaranteed full re-fetch
      }, ms);
    }

    start();

    return () => {
      clearInterval(intervalRef.current!);
      clearTimeout(timeoutRef.current!);
    };
  }, [enabled, intervalSec]);

  if (!enabled) return null;

  return (
    <div className="bg-green-100 w-full">
      <div
        className="bg-green-400 h-1 transition-all duration-75 ease-linear"
        style={{ width: `${Math.max(0, pct)}%` }}
      />
    </div>
  );
}