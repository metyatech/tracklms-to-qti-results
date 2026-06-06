import eslintConfigPrettier from "eslint-config-prettier";
import tseslint from "typescript-eslint";

export default tseslint.config(...tseslint.configs.recommended, eslintConfigPrettier, {
  ignores: ["dist/**", "node_modules/**", "tests/.tmp_cli/**"],
});
