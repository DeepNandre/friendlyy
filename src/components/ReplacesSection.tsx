const tools = [
  "Calendly", "Cal.com", "Cluely", "Fathom", "Fellow.app",
  "Fireflies.ai", "Followup.cc", "Fyxer", "Grain", "Granola",
  "Motion", "Otter.ai", "Jace.ai", "Superhuman",
];

const ReplacesSection = () => {
  return (
    <section className="py-20 bg-background overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 text-center">
        <h2 className="font-serif text-4xl md:text-6xl font-normal text-foreground mb-12 leading-tight">
          Quin replaces
        </h2>

        <div className="flex flex-wrap justify-center gap-3">
          {tools.map((tool, i) => (
            <div
              key={i}
              className="px-5 py-2.5 rounded-full border border-border text-sm font-sans text-foreground"
            >
              {tool}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ReplacesSection;
