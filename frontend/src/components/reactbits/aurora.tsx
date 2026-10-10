"use client";

import React, { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

interface AuroraProps {
  colorStops?: string[];
  amplitude?: number;
  blend?: number;
  className?: string;
}

export const Aurora: React.FC<AuroraProps> = ({
  colorStops = ["#38bdf8", "#818cf8", "#c084fc"],
  amplitude = 1.0,
  className = "",
}) => {
  return (
    <div
      className={cn(
        "absolute inset-0 overflow-hidden pointer-events-none opacity-40 dark:opacity-60",
        className
      )}
      aria-hidden="true"
    >
      <div
        className="absolute -top-[50%] -left-[50%] w-[200%] h-[200%] animate-spin-slow"
        style={{
          background: `radial-gradient(circle at 30% 30%, ${colorStops[0]} 0%, transparent 40%),
                       radial-gradient(circle at 70% 60%, ${colorStops[1]} 0%, transparent 40%),
                       radial-gradient(circle at 40% 80%, ${colorStops[2]} 0%, transparent 40%)`,
          filter: "blur(60px)",
          transformOrigin: "center center",
          animationDuration: "25s",
        }}
      />
    </div>
  );
};

