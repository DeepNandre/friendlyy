import { useState } from "react";

const solutions = [
  {
    label: "Financial advisors",
    desc: "Stay focused on clients while Quin turns conversations into notes, records, and action items—automatically.",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/68d5aaf849be6d6702cf768f_0d597d85805b6f1c950e30c45ef8461a_solutions-financial-advisors.avif",
  },
  {
    label: "Sales",
    desc: "Close faster with Quin capturing meeting details, updating your CRM, and setting next steps.",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/68d5b55a5ac89d17a739bbf3_0250d812903a97ec62762d75defbbfb3_solutions-sales.avif",
  },
  {
    label: "Executives",
    desc: "Quin preps briefs, drafts responses, and tracks follow-ups—so you can focus on leading.",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/68d5b55a91414e9c91dc96a7_8e0c48e451f10fa3c56efcc3ccd7c2cd_solutions-executives.avif",
  },
  {
    label: "Recruiters",
    desc: "Keep candidates engaged with Quin turning interview notes into updates, feedback, and next steps.",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/68d5b55e51ecd1977651afae_f9f055db56a483317f1d1fbe5348320d_solutions-recruiters.avif",
  },
  {
    label: "Assistants",
    desc: "Quin handles notes, scheduling, and emails—helping you keep everything organized and on time.",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/68d5b55a96022d818b3302cd_442e2ef2038d32e38dd6db06a9974493_solutions-assistants.avif",
  },
  {
    label: "Insurance agents",
    desc: "Client details, coverage notes, family changes—everything ends up in the right record.",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/696ff07b1d8c18678d4bbdec_99faed4781ff649afd39654fbf85eae1_solutions-insurance-agents.avif",
  },
  {
    label: "Real estate agents",
    desc: "Quin handles the admin that piles up between showings.",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/696ff1b5bda5966cc536963a_693d9f175bc542ff61aa4989f347bc8c_solutions-real-estate-agents.avif",
  },
];

const SolutionsSection = () => {
  const [active, setActive] = useState(0);

  return (
    <section className="py-20 bg-background">
      <div className="max-w-7xl mx-auto px-6">
        <p className="font-sans text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-4">Who Uses Quin</p>
        <h2 className="font-serif text-4xl md:text-5xl font-normal text-foreground mb-12 leading-tight max-w-2xl">
          Built for people who drive the business forward
        </h2>
        <p className="font-sans text-base text-muted-foreground mb-12 max-w-xl -mt-8">
          Quin supports the people who keep everything moving, from the first meeting to the final follow-up.
        </p>

        <div className="flex flex-col lg:flex-row gap-8">
          {/* Left: tab list */}
          <div className="lg:w-80 flex-shrink-0 space-y-1">
            {solutions.map((s, i) => (
              <button
                key={i}
                onClick={() => setActive(i)}
                className={`w-full text-left px-4 py-4 rounded-xl transition-all ${
                  i === active
                    ? "bg-foreground text-background"
                    : "hover:bg-muted text-foreground"
                }`}
              >
                <div className={`font-sans font-semibold text-sm mb-1 ${i === active ? "text-background" : "text-foreground"}`}>
                  {s.label}
                </div>
                {i === active && (
                  <div className="font-sans text-xs text-background/70 mt-1">{s.desc}</div>
                )}
                {i === active && (
                  <a href="#" className={`inline-flex items-center gap-1 text-xs font-semibold mt-3 ${i === active ? "text-[hsl(var(--accent))]" : ""}`}>
                    Learn more →
                  </a>
                )}
              </button>
            ))}
          </div>

          {/* Right: image */}
          <div className="flex-1">
            <img
              key={active}
              src={solutions[active].image}
              alt={solutions[active].label}
              className="w-full h-[500px] object-cover rounded-2xl animate-slide-up"
            />
          </div>
        </div>
      </div>
    </section>
  );
};

export default SolutionsSection;
