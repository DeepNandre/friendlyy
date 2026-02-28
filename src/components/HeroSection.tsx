import { useState } from "react";

const tabs = [
  { label: "Meeting prep", image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a3b4c439cf7111aa91545_hero-meeting-prep.avif" },
  { label: "Note-taking", image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a3b4cfa14d8675cbe965b_hero-note-taking.avif" },
  { label: "Follow-ups", image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a3b4bbef70d6309ad00fb_hero-follow-ups.avif" },
  { label: "Data entry", image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a3b4c1aa8f027a61922ed_hero-data-entry.avif" },
  { label: "Scheduling", image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a3b4bdb72b8cad5680061_hero-scheduling.avif" },
  { label: "Search", image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a3b4c450a52a43e507bcb_hero-search.avif" },
  { label: "And more...", image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a3b4be906661f4dee1416_hero-and-more.avif" },
];

const HeroSection = () => {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <section className="bg-background pt-16 pb-0">
      <div className="max-w-5xl mx-auto px-6 text-center">
        <h1 className="font-serif text-6xl md:text-7xl lg:text-8xl font-normal text-foreground leading-tight mb-6">
          You say it.<br />It's sorted.
        </h1>
        <p className="font-sans text-lg text-muted-foreground max-w-xl mx-auto mb-10">
          Friendly handles the annoying stuff for you — phone calls, quotes, bookings, cancellations. Just type what you need like texting a friend.
        </p>

        {/* Tabs */}
        <div className="flex flex-wrap justify-center gap-0 border-b border-border mb-0 overflow-x-auto scrollbar-hide">
          {tabs.map((tab, i) => (
            <button
              key={i}
              onClick={() => setActiveTab(i)}
              className={`px-5 py-3 text-sm font-sans font-medium border-b-2 whitespace-nowrap transition-colors ${
                i === activeTab
                  ? "border-foreground bg-[hsl(var(--accent))] text-foreground border-b-0 rounded-t-sm"
                  : "border-transparent text-foreground hover:text-muted-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* Hero Image */}
        <div className="w-full overflow-hidden">
          <img
            src={tabs[activeTab].image}
            alt={tabs[activeTab].label}
            className="w-full object-cover animate-slide-up"
            key={activeTab}
          />
        </div>
      </div>

      {/* CTAs */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-4 py-10">
        <button className="px-6 py-3 rounded-full border-2 border-foreground bg-transparent text-sm font-semibold font-sans hover:bg-foreground hover:text-background transition-colors">
          Watch Demo
        </button>
        <a
          href="/chat"
          className="px-6 py-3 rounded-full bg-foreground text-background text-sm font-semibold font-sans hover:opacity-80 transition-opacity"
        >
          Try Friendly Free
        </a>
      </div>
    </section>
  );
};

export default HeroSection;
