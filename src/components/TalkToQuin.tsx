import { useState } from "react";

const channels = [
  {
    label: "In-app",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/699f3d39cfd3f6a4d3a8cf56_talk-app.avif",
  },
  {
    label: "SMS",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a84702b2e6c809d31f5c3_talk-sms.avif",
  },
  {
    label: "Email",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a8470244709abd2709612_talk-email.avif",
  },
  {
    label: "Slack",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a8470d46fba512309bdbf_talk-slack.avif",
  },
  {
    label: "Teams",
    image: "https://cdn.prod.website-files.com/66563d83090173fa830e5776/688a847016339691baf7361f_talk-teams.avif",
  },
];

const TalkToQuin = () => {
  const [active, setActive] = useState(0);

  return (
    <section className="py-20 bg-background">
      <div className="max-w-5xl mx-auto px-6 text-center">
        <p className="font-sans text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-4">Talk to Quin</p>
        <h2 className="font-serif text-4xl md:text-5xl font-normal text-foreground mb-4 leading-tight">
          Available anytime, anywhere
        </h2>
        <p className="font-sans text-base text-muted-foreground mb-10 max-w-lg mx-auto">
          Always there for you. Works wherever you do. The only assistant available 24/7.
        </p>

        {/* Tabs */}
        <div className="flex justify-center gap-2 mb-8 flex-wrap">
          {channels.map((c, i) => (
            <button
              key={i}
              onClick={() => setActive(i)}
              className={`px-5 py-2 rounded-full text-sm font-sans font-medium transition-colors ${
                i === active
                  ? "bg-foreground text-background"
                  : "bg-muted text-foreground hover:bg-border"
              }`}
            >
              {c.label}
            </button>
          ))}
        </div>

        <img
          key={active}
          src={channels[active].image}
          alt={channels[active].label}
          className="w-full rounded-2xl object-cover animate-slide-up shadow-xl"
        />
      </div>
    </section>
  );
};

export default TalkToQuin;
