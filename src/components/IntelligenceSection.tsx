const blogPosts = [
  "How AI voice agents are changing customer service",
  "Why parallel calling gets you better quotes",
  "The psychology of phone anxiety (and how to beat it)",
  "How Friendly navigates phone menus automatically",
  "5 calls you should never make yourself again",
  "The hidden cost of waiting on hold",
  "How we built voice agents that businesses trust",
  "Introducing Blitz: parallel calling for instant quotes",
  "Built at Mistral Hackathon 2026",
];

const IntelligenceSection = () => {
  return (
    <section className="py-20 bg-background">
      <div className="max-w-7xl mx-auto px-6">
        <p className="font-sans text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-4">Intelligence</p>
        <div className="flex flex-col lg:flex-row gap-12 items-start">
          {/* Left */}
          <div className="lg:w-1/2">
            <h2 className="font-serif text-4xl md:text-5xl font-normal text-foreground mb-6 leading-tight">
              More than just a chatbot
            </h2>
            <p className="font-sans text-base text-muted-foreground mb-8 max-w-md">
              Friendly doesn't just answer questions — it takes action. Real phone calls. Real bookings. Real results. Powered by Mistral AI and built to handle the stuff you've been putting off.
            </p>
            <img
              src="https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a46361a5888a9d71f7ce3_businesswoman.avif"
              alt="Intelligence"
              className="w-full rounded-2xl object-cover"
            />
          </div>

          {/* Right: Blog posts */}
          <div className="lg:w-1/2">
            <div className="space-y-0">
              {blogPosts.map((post, i) => (
                <a
                  key={i}
                  href="#"
                  className="flex items-center justify-between py-4 border-b border-border hover:text-muted-foreground group transition-colors"
                >
                  <span className="font-sans text-sm font-medium text-foreground group-hover:text-muted-foreground pr-4">{post}</span>
                  <span className="font-sans text-muted-foreground flex-shrink-0">→</span>
                </a>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};

export default IntelligenceSection;
