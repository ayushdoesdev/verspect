"use client";

import Link from "next/link";
import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";
import { BLOG_POSTS } from "@/lib/blog";

export default function BlogPage() {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />
      <section className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
        <h1 className="font-[family-name:var(--font-display)] text-4xl font-semibold text-white">Blog</h1>
        <div className="mt-10 space-y-6">
          {BLOG_POSTS.map((p) => (
            <article key={p.slug} className="rounded-xl border border-white/10 bg-white/[0.03] p-5">
              <h2 className="text-lg font-semibold text-white">{p.title}</h2>
              <p className="mt-2 text-sm text-slate-400">{p.excerpt}</p>
              <Link href={`/blog/${p.slug}`} className="mt-3 inline-block text-sm text-teal-300">
                Read more
              </Link>
            </article>
          ))}
        </div>
      </section>
      <MarketingFooter />
    </div>
  );
}
