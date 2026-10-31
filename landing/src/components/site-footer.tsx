import Link from "next/link";
import { BrandMark } from "@/components/site-nav";

const repo = "https://github.com/ayushdoesdev/verspect";

export function SiteFooter() {
  return <footer className="footer">
    <div className="footer-grid">
      <div className="footer-brand-col">
        <Link href="#top" className="brand"><span className="brand-mark"><BrandMark /></span><span>Verspect</span></Link>
        <p>Dependency intelligence for GitHub repositories.</p>
        <span className="footer-license">Open source · Apache-2.0</span>
      </div>
      <FooterColumn title="Product" links={[["Features", "#features"], ["Ecosystems", "#ecosystems"], ["Self-hosting", "#self-hosting"], ["FAQ", "#faq"]]} />
      <FooterColumn title="Resources" links={[["Documentation / README", `${repo}#readme`], ["GitHub Releases", `${repo}/releases`], ["Issues", `${repo}/issues`], ["Contributing", `${repo}/blob/main/CONTRIBUTING.md`]]} />
      <FooterColumn title="Project" links={[["Repository", repo], ["Apache-2.0 License", `${repo}/blob/main/LICENSE`], ["Third-party Notices", `${repo}/blob/main/THIRD_PARTY_NOTICES.md`], ["Security Policy", `${repo}/blob/main/SECURITY.md`]]} />
    </div>
    <div className="footer-bottom"><span>© {new Date().getFullYear()} Verspect contributors</span><span>Verspect name, logo, and official branding are reserved.</span></div>
  </footer>;
}

function FooterColumn({ title, links }: { title: string; links: [string, string][] }) {
  return <div className="footer-column"><h2>{title}</h2>{links.map(([label, href]) => href.startsWith("#") ? <Link key={label} href={href}>{label}</Link> : <a key={label} href={href} target="_blank" rel="noreferrer noopener">{label}<span aria-hidden="true"> ↗</span></a>)}</div>;
}
