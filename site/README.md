# ETHarcade.fun landing page

Run `npm install` and `npm run dev`. Build the deployable site with `npm run build`.

## SDK documentation on the same origin

The complete SDK docs site is served at `/docs/`, including its sidebar,
search index, examples, source pages, theme switch, and mobile navigation.
The landing page's Docs link and SDK resources point there.

`predev` and `prebuild` copy the committed `../sdk/web/dist/` site into
`public/docs/`, so the production output includes `dist/docs/`. Deploy the
entire `site/dist/` directory. Serve existing static files before any SPA
fallback so `/docs/*.html`, scripts, and styles remain accessible.

After changing SDK Markdown or Python source, run `npm run docs:generate`
(Python 3 required) and commit the regenerated `sdk/web/dist/` files. Normal
landing-page builds only need Node, using that committed documentation build.
The copied `public/docs/` directory is generated and ignored by Git.
