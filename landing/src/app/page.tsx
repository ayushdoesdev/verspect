import { MarketingFooter, MarketingNav } from "@/components/marketing/nav";
import { LandingHero } from "@/components/marketing/landing/hero";
import { ScanDemoSection } from "@/components/marketing/landing/scan-demo";
import { SimulatorDemoSection } from "@/components/marketing/landing/simulator-demo";
import { MigrationDemoSection } from "@/components/marketing/landing/migration-demo";
import { DependencyGraphSection } from "@/components/marketing/landing/dependency-graph";
import { SecurityDashboardSection } from "@/components/marketing/landing/security-dashboard";
import { ProductGallerySection } from "@/components/marketing/landing/product-gallery";
import { FaqSection, FinalCtaSection, RoadmapTeaserSection } from "@/components/marketing/landing/social-sections";

export default function Home() {
  return (
    <div className="min-h-screen bg-[#070b12] text-slate-100">
      <MarketingNav />
      <main>
        <LandingHero />
        <ProductGallerySection />
        <ScanDemoSection />
        <SimulatorDemoSection />
        <MigrationDemoSection />
        <DependencyGraphSection />
        <SecurityDashboardSection />
        <RoadmapTeaserSection />
        <FaqSection />
        <FinalCtaSection />
      </main>
      <MarketingFooter />
    </div>
  );
}
