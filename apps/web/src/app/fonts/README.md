# Self-hosted fonts

Inter, JetBrains Mono and Newsreader, latin subset, variable weight axes.

These are served from the repo rather than fetched by `next/font/google`, which
downloads every face from `fonts.gstatic.com` **at build time**. That made
releases non-deterministic: the v1.36.1 deploy failed when Google answered 404
for the Newsreader `woff2` files mid-build and Turbopack aborted with 12
`Module not found` errors. Nothing in the commit was at fault, and re-running
the same job succeeded — which is exactly why it needed removing.

All three are variable fonts, so the full latin subset is 206 KB across four
files. Newsreader alone previously pulled eight static faces (4 weights × 2
styles) at build time.

## Licence

All three are licensed under the SIL Open Font License 1.1, which permits
redistribution and bundling:

- Inter — https://github.com/rsms/inter
- JetBrains Mono — https://github.com/JetBrains/JetBrainsMono
- Newsreader — https://github.com/productiontype/Newsreader

## Refreshing

Re-download the latin subset from the Google Fonts CSS API with a modern
browser User-Agent (it serves `woff2` only to browsers that support it), keeping
the `@font-face` block whose `unicode-range` covers `U+0000-00FF`.
