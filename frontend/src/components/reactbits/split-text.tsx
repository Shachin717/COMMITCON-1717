"use client";

import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface SplitTextProps {
  text: string;
  className?: string;
  delay?: number;
  animationFrom?: Record<string, any>;
  animationTo?: Record<string, any>;
}

export const SplitText: React.FC<SplitTextProps> = ({
  text,
  className = "",
  delay = 30,
  animationFrom = { opacity: 0, transform: "translate3d(0,20px,0)" },
  animationTo = { opacity: 1, transform: "translate3d(0,0,0)" },
}) => {
  const letters = text.split("");

  return (
    <span className={cn("inline-block overflow-hidden", className)}>
      {letters.map((letter, index) => (
        <motion.span
          key={index}
          initial={animationFrom}
          animate={animationTo}
          transition={{
            duration: 0.4,
            delay: (index * delay) / 1000,
            ease: [0.2, 0.65, 0.3, 0.9],
          }}
          className="inline-block whitespace-pre"
        >
          {letter}
        </motion.span>
      ))}
    </span>
  );
};

