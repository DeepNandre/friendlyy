const features = [
  {
    title: "SOC 2 compliant",
    desc: "SOC 2 compliance protocols ensure secure and compliant data handling.",
  },
  {
    title: "Robust encryption",
    desc: "AES-256 for storage and TLS 1.2/1.3 for secure communication.",
  },
  {
    title: "GDPR compliant",
    desc: "GDPR-compliant practices guarantee safe and secure data usage.",
  },
  {
    title: "Enterprise ready",
    desc: "Role-based access with SSO and audit tracking ensure secure, organized, and compliant team operations.",
  },
];

const SecuritySection = () => {
  return (
    <section className="py-20 bg-muted">
      <div className="max-w-7xl mx-auto px-6">
        <p className="font-sans text-xs font-semibold uppercase tracking-widest text-muted-foreground mb-4">Security</p>
        <div className="flex flex-col lg:flex-row gap-12 items-center">
          <div className="lg:w-1/2">
            <h2 className="font-serif text-4xl md:text-5xl font-normal text-foreground mb-8 leading-tight">
              Your information stays where it belongs
            </h2>
            <p className="font-sans text-base text-muted-foreground mb-10">
              Friendly works with your data but never stores it, using enterprise-grade protection for each secure interaction.
            </p>

            <div className="space-y-6">
              {features.map((f, i) => (
                <div key={i} className="flex gap-4">
                  <div className="w-5 h-5 rounded-full bg-[hsl(var(--accent))] flex-shrink-0 mt-1 flex items-center justify-center">
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                      <path d="M1.5 4L3.5 6L6.5 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                  <div>
                    <h4 className="font-sans font-semibold text-sm text-foreground mb-1">{f.title}</h4>
                    <p className="font-sans text-sm text-muted-foreground">{f.desc}</p>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex flex-col sm:flex-row items-start gap-4 mt-10">
              <button className="px-6 py-3 rounded-full border-2 border-foreground bg-transparent text-sm font-semibold font-sans hover:bg-foreground hover:text-background transition-colors">
                Get Demo
              </button>
              <a
                href="#"
                className="px-6 py-3 rounded-full bg-foreground text-background text-sm font-semibold font-sans hover:opacity-80 transition-opacity"
              >
                Get Started
              </a>
            </div>
          </div>

          <div className="lg:w-1/2">
            <img
              src="https://cdn.prod.website-files.com/66563d83090173fa830e5776/699f339a2fdbcfe2b6533548_integrations-security.avif"
              alt="Security"
              className="w-full rounded-2xl object-cover"
            />
          </div>
        </div>
      </div>
    </section>
  );
};

export default SecuritySection;
