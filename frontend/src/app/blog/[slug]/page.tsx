import Link from "next/link";
import { notFound } from "next/navigation";
import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";
import { BLOG_POSTS, getBlogPost } from "@/lib/blog";

export function generateStaticParams() {
  return BLOG_POSTS.map((post) => ({ slug: post.slug }));
}

export default async function BlogPostPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  const post = getBlogPost(slug);
  if (!post) notFound();

  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />
      <article className="mx-auto max-w-3xl px-4 py-20 sm:px-6">
        <Link href="/blog" className="text-sm text-teal-300 hover:underline">
          ← Blog
        </Link>
        <p className="mt-6 text-xs uppercase tracking-wide text-slate-500">{post.date}</p>
        <h1 className="mt-2 font-[family-name:var(--font-display)] text-4xl font-semibold text-white">
          {post.title}
        </h1>
        <p className="mt-4 text-slate-400">{post.excerpt}</p>
        <div className="mt-8 space-y-4 text-sm leading-relaxed text-slate-300">
          {post.body.map((paragraph) => (
            <p key={paragraph.slice(0, 24)}>{paragraph}</p>
          ))}
        </div>
      </article>
      <MarketingFooter />
    </div>
  );
}
