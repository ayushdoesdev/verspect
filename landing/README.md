# Verspect public website

This is the independent public marketing website for Verspect. It is a standalone Next.js App Router project in `landing/`; the application and its existing marketing site in `frontend/` are separate projects.

## Local development

Use Node.js 20.9 or newer and npm. From this directory:

```bash
npm install
npm run dev
```

Open <http://localhost:3000>. The website does not need environment variables, authentication, a database, or the Verspect API to render. Optionally set `NEXT_PUBLIC_SITE_URL` to the deployed public origin for sitemap metadata; otherwise, Vercel's deployment URL is used (and local development defaults to localhost).

## Checks and production build

```bash
npm run lint
npm run typecheck
npm run build
npm start
```

## Vercel deployment

Create a separate Vercel project connected to `ayushdoesdev/verspect`. Set its **Root Directory** to `landing` and select **Next.js**. Use `npm run build` as the build command and the default npm install command; Vercel reads this directory's `package.json` and lockfile. No environment variables are required to render the site.

The original self-hostable Verspect application and its existing marketing site remain in `frontend/`, `backend/`, and `worker/` and are deployed independently. This project is only the public website; it does not connect to the application API.
