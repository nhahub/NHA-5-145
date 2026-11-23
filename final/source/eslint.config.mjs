import eslint from "@eslint/js";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "**/.venv/**",
      "**/dist/**",
      "**/node_modules/**",
      "outputs/**",
      "work/**",
      // Flat config does not read .gitignore: local backups and generated deliverables.
      ".scratch/**",
      // Local, untracked tool folders.
      ".*/**",
      "output/**",
    ],
  },
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ["**/*.ts", "**/*.tsx"],
    languageOptions: {
      parserOptions: {
        projectService: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
  },
);
