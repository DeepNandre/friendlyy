const Footer = () => {
  return (
    <footer className="bg-foreground text-background py-16">
      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10 mb-12">
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2 mb-4">
              <div className="w-7 h-7 rounded-lg bg-[hsl(220,70%,55%)] flex items-center justify-center">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10"/>
                  <path d="M12 2a10 10 0 0 1 0 20"/>
                  <path d="M2 12h20"/>
                </svg>
              </div>
              <span className="font-serif text-lg text-background">Friendly</span>
            </div>
            <p className="font-sans text-xs text-background/50 max-w-xs">
              Meet your dream assistant. Handles everything a great assistant would.
            </p>
          </div>

          <div>
            <h4 className="font-sans font-semibold text-xs uppercase tracking-widest text-background/50 mb-4">Product</h4>
            <div className="space-y-2">
              {["Features", "Integrations", "Skills", "Pricing", "Changelog"].map((item) => (
                <a key={item} href="#" className="block font-sans text-sm text-background/70 hover:text-background transition-colors">{item}</a>
              ))}
            </div>
          </div>

          <div>
            <h4 className="font-sans font-semibold text-xs uppercase tracking-widest text-background/50 mb-4">Solutions</h4>
            <div className="space-y-2">
              {["Financial Advisors", "Sales", "Executives", "Recruiters", "Assistants"].map((item) => (
                <a key={item} href="#" className="block font-sans text-sm text-background/70 hover:text-background transition-colors">{item}</a>
              ))}
            </div>
          </div>

          <div>
            <h4 className="font-sans font-semibold text-xs uppercase tracking-widest text-background/50 mb-4">Company</h4>
            <div className="space-y-2">
              {["About", "Blog", "Careers", "Security", "Privacy", "Terms"].map((item) => (
                <a key={item} href="#" className="block font-sans text-sm text-background/70 hover:text-background transition-colors">{item}</a>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t border-background/10 pt-8 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="font-sans text-xs text-background/40">© 2025 Friendly. All rights reserved.</p>
          <div className="flex gap-6">
            <a href="#" className="font-sans text-xs text-background/40 hover:text-background transition-colors">Privacy Policy</a>
            <a href="#" className="font-sans text-xs text-background/40 hover:text-background transition-colors">Terms of Service</a>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
