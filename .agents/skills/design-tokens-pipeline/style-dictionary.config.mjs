// style-dictionary.config.mjs — ready-to-run Style Dictionary v4 config wired
// with @tokens-studio/sd-transforms. This is the TRANSFORM stage of the spine:
//   Tokens Studio JSON (Git = source of truth)
//     -> @tokens-studio/sd-transforms (the REQUIRED glue, FIGMA-SETUP §3)
//     -> Style Dictionary
//     -> platform outputs (CSS vars / SCSS / JS)
//
// Install (once, in the repo that owns the tokens — NOT globally):
//   npm i -D style-dictionary @tokens-studio/sd-transforms
// Build:
//   node -e "import('style-dictionary').then(async ({default:SD})=>{ \
//     const {register}=await import('@tokens-studio/sd-transforms'); \
//     register(SD); const sd=new SD('./style-dictionary.config.mjs'); \
//     await sd.buildAllPlatforms(); })"
// Or add an npm script (see SKILL.md "Wire it into the repo").
//
// `register(StyleDictionary)` MUST run before the config is consumed — it adds
// the `tokens-studio` transformGroup and the `ts/*` transforms. Point `source`
// at the JSON your Tokens Studio plugin pushes (single file or a folder glob).

export default {
  source: ["tokens/**/*.json"], // <-- where Tokens Studio writes; adjust per repo
  preprocessors: ["tokens-studio"], // resolve TS aliases/math before transform
  platforms: {
    css: {
      transformGroup: "tokens-studio",
      transforms: ["name/kebab"], // css var names like --color-primary-500
      buildPath: "build/css/",
      files: [
        {
          destination: "tokens.css",
          format: "css/variables",
          options: { outputReferences: true }, // keep var(--x) refs = revertable
        },
      ],
    },
    scss: {
      transformGroup: "tokens-studio",
      transforms: ["name/kebab"],
      buildPath: "build/scss/",
      files: [{ destination: "_tokens.scss", format: "scss/variables" }],
    },
    js: {
      transformGroup: "tokens-studio",
      transforms: ["name/camel"],
      buildPath: "build/js/",
      files: [{ destination: "tokens.js", format: "javascript/es6" }],
    },
  },
};
