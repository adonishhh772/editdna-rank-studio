import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{js,ts,jsx,tsx,mdx}", "./components/**/*.{js,ts,jsx,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        space: "#0a0a1a",
        neonBlue: "#3b82f6",
        neonPurple: "#8b5cf6",
        neonGreen: "#10b981",
      },
    },
  },
  plugins: [],
};

export default config;
