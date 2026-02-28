const skills = [
  "Call multiple businesses and get quotes in parallel",
  "Navigate phone menus and wait on hold for you",
  "Cancel subscriptions by calling customer service",
  "Book appointments at doctors, dentists, restaurants",
  "Negotiate bills and get better rates",
  "Find available services in your area",
  "Compare prices across multiple providers",
  "Schedule callbacks when lines are busy",
  "Follow up on pending requests automatically",
];

const SkillsSection = () => {
  return (
    <section className="py-20 bg-background overflow-hidden">
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex flex-col lg:flex-row gap-16 items-start">
          {/* Left: Scrolling skills */}
          <div className="flex-1 min-w-0">
            <p className="font-sans text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-4">Skills</p>
            <h2 className="font-serif text-4xl md:text-5xl font-normal text-foreground mb-4 leading-tight">
              Say goodbye to<br />busy work, forever
            </h2>
            <p className="font-sans text-base text-muted-foreground mb-8 max-w-sm">
              Friendly learns your preferences and handles calls the way you would, keeping everything organized without the phone anxiety.
            </p>

            {/* Skills list */}
            <div className="space-y-2 mb-6">
              {skills.slice(0, 9).map((skill, i) => (
                <div key={i} className="flex items-center gap-3 py-2 border-b border-border last:border-0">
                  <span className="w-4 h-4 rounded-full bg-[hsl(var(--accent))] flex-shrink-0 flex items-center justify-center">
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                      <path d="M1.5 4L3.5 6L6.5 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </span>
                  <span className="font-sans text-sm font-medium text-foreground">{skill}</span>
                </div>
              ))}
            </div>

            <div className="text-sm font-sans font-semibold text-muted-foreground mb-4">AI agents that make real phone calls for you</div>
            <a href="#" className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border-2 border-foreground text-sm font-semibold font-sans hover:bg-foreground hover:text-background transition-colors">
              Explore Skills →
            </a>
          </div>

          {/* Right: Image */}
          <div className="flex-1 min-w-0">
            <img
              src="https://cdn.prod.website-files.com/66563d83090173fa830e5776/699f40f9359f8b7f293181ef_no-more-busywork.avif"
              alt="No more busy work"
              className="w-full rounded-2xl object-cover"
            />
          </div>
        </div>
      </div>
    </section>
  );
};

export default SkillsSection;
