const blogPosts = [
  "Bad prep is usually why calls go sideways",
  "Building workflows for your specific routine",
  "Introducing the new Quin",
  "Why transcription isn't the same as assistance",
  "How to set up a high-converting scheduling flow",
  "The 7 automations every advisor should turn on in Quin",
  "Stop paying the 'Tool Tax': Quin replaces 5 subscriptions",
  "Less work. More consistency. Templates are here.",
  "Record meetings anywhere with Quin's upgraded in-person notetaker",
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
              More than just a meeting assistant
            </h2>
            <p className="font-sans text-base text-muted-foreground mb-8 max-w-md">
              Quin doesn't just complete tasks - it knows how you want to get them done. Set your preferences once and Quin makes decisions the way you would, handling work like someone who's worked with you for years.
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
