import { useState } from "react";

const PricingSection = () => {
  const [hours, setHours] = useState(10);

  const price = Math.round(hours * 4.9);

  return (
    <section className="py-20 bg-background" id="pricing">
      <div className="max-w-4xl mx-auto px-6">
        <p className="font-sans text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-4 text-center">Pricing</p>
        <h2 className="font-serif text-4xl md:text-5xl font-normal text-foreground mb-4 leading-tight text-center">
          Get Quin free for 2 weeks
        </h2>
        <p className="font-sans text-base text-muted-foreground mb-12 max-w-xl mx-auto text-center">
          Get started free for 14 days. Whether it's just you or your whole team, Quin gives you the same smart features to handle notes, follow-ups, and updates—automatically.
        </p>

        <div className="grid md:grid-cols-2 gap-8">
          {/* Individual Plan */}
          <div className="bg-card rounded-2xl border border-border p-8">
            <h3 className="font-sans font-semibold text-sm text-muted-foreground mb-6">
              How much time do you waste on admin tasks each month?
            </h3>

            <div className="mb-6">
              <div className="flex justify-between mb-2">
                <span className="font-sans text-sm text-muted-foreground">Admin hours/month</span>
                <span className="font-sans font-bold text-foreground">{hours} HRS</span>
              </div>
              <input
                type="range"
                min={1}
                max={40}
                value={hours}
                onChange={(e) => setHours(Number(e.target.value))}
                className="w-full accent-[hsl(var(--accent))] h-2"
              />
            </div>

            <div className="mb-6">
              <div className="flex items-baseline gap-1">
                <span className="font-sans text-2xl font-light">$</span>
                <span className="font-serif text-6xl font-normal">{price}</span>
                <span className="font-sans text-sm text-muted-foreground">per month</span>
              </div>
            </div>

            <div className="space-y-3 mb-8">
              <h4 className="font-sans font-semibold text-sm text-foreground">What Quin takes off your plate</h4>
              {[
                `Summarizes ~${hours} meetings`,
                `Drafts ~${hours * 10} emails/follow-ups`,
                `Automates ~${hours * 25} repetitive tasks`,
                "and so much more...",
              ].map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-4 h-4 rounded-full bg-[hsl(var(--accent))] flex-shrink-0 flex items-center justify-center">
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                      <path d="M1.5 4L3.5 6L6.5 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </span>
                  <span className="font-sans text-sm text-foreground">{item}</span>
                </div>
              ))}
            </div>

            <p className="font-sans text-xs text-muted-foreground mb-6">All plans include unlimited users</p>

            <a
              href="#"
              className="block w-full py-3 rounded-full bg-foreground text-background text-sm font-semibold font-sans text-center hover:opacity-80 transition-opacity"
            >
              Free 14 day trial
            </a>
          </div>

          {/* Enterprise */}
          <div className="bg-foreground rounded-2xl p-8 flex flex-col">
            <h3 className="font-serif text-2xl font-normal text-background mb-4">Enterprise</h3>
            <p className="font-sans text-sm text-background/70 mb-8">
              A smart assistant tailored to your systems, scale, and security needs.
            </p>

            <div className="space-y-3 mb-8 flex-1">
              {["Automation without limits", "Custom pricing", "Automate everything"].map((item, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span className="w-4 h-4 rounded-full bg-[hsl(var(--accent))] flex-shrink-0 flex items-center justify-center">
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                      <path d="M1.5 4L3.5 6L6.5 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </span>
                  <span className="font-sans text-sm text-background">{item}</span>
                </div>
              ))}
            </div>

            <a
              href="mailto:gabe@heyquin.io?subject=Enterprise pricing"
              className="block w-full py-3 rounded-full bg-[hsl(var(--accent))] text-foreground text-sm font-semibold font-sans text-center hover:opacity-80 transition-opacity"
            >
              Contact us
            </a>
          </div>
        </div>
      </div>
    </section>
  );
};

export default PricingSection;
