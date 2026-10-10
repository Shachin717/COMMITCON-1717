"use client";

import React from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface BlurTextProps {
  text: string;
  delay?: number;
  className?: string;
  animateBy?: "words" | "letters";
  direction?: "top" | "bottom";
  threshold?: number;
  rootMargin?: string;
}

export const BlurText: React.FC<BlurTextProps> = ({
  text,
  delay = 50,
  className = "",
  animateBy = "words",
  direction = "top",
}) => {
  const elements = animateBy === "words" ? text.split(" ") : text.split("");

  return (
    <span aria-label={text} className={cn("inline-flex flex-wrap gap-x-1.5", className)}>
      <span className="sr-only">{text}</span>
      <span aria-hidden="true" className="inline-flex justify-center flex-wrap gap-x-1.5">
        {elements.map((el, i) => (
          <motion.span
            key={i}
            initial={{
              filter: "blur(10px)",
              opacity: 0,
              y: direction === "top" ? -12 : 12,
            }}
            animate={{
              filter: "blur(0px)",
              opacity: 1,
              y: 0,
            }}
            transition={{
              duration: 0.45,
              delay: (i * delay) / 1000,
              ease: [0.25, 0.1, 0.25, 1],
            }}
            className="inline-block"
          >
            {el}
          </motion.span>
        ))}
      </span>
    </span>
  );
};

