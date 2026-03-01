import { useState } from "react";
import { ChevronDown } from "lucide-react";
import FriendlyLogo from "@/components/FriendlyLogo";

const Navbar = () => {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <nav className="sticky top-0 z-50 bg-background border-b border-border">
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo */}
        <a href="#" className="flex items-center">
          <FriendlyLogo size="md" />
        </a>

        {/* Desktop Nav */}
        <div className="hidden md:flex items-center gap-8">
          <button className="flex items-center gap-1 text-sm font-sans text-foreground hover:text-muted-foreground transition-colors">
            Product <ChevronDown className="w-3.5 h-3.5" />
          </button>
          <a href="#" className="text-sm font-sans text-foreground hover:text-muted-foreground transition-colors">Blog</a>
          <button className="flex items-center gap-1 text-sm font-sans text-foreground hover:text-muted-foreground transition-colors">
            Solutions <ChevronDown className="w-3.5 h-3.5" />
          </button>
          <a href="#" className="text-sm font-sans text-foreground hover:text-muted-foreground transition-colors">Pricing</a>
          <a href="#" className="text-sm font-sans text-foreground hover:text-muted-foreground transition-colors">Login</a>
        </div>

        {/* CTA */}
        <div className="hidden md:flex items-center gap-3">
          <a
            href="/dashboard"
            className="px-5 py-2 rounded-full border-2 border-foreground bg-transparent text-sm font-semibold font-sans hover:bg-foreground hover:text-background transition-colors"
          >
            GET STARTED
          </a>
        </div>

        {/* Mobile Menu Button */}
        <button className="md:hidden" onClick={() => setMobileOpen(!mobileOpen)}>
          <div className="w-6 h-0.5 bg-foreground mb-1.5"></div>
          <div className="w-6 h-0.5 bg-foreground mb-1.5"></div>
          <div className="w-6 h-0.5 bg-foreground"></div>
        </button>
      </div>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div className="md:hidden bg-background border-t border-border px-6 py-4 flex flex-col gap-4">
          <a href="#" className="text-sm font-sans">Product</a>
          <a href="#" className="text-sm font-sans">Blog</a>
          <a href="#" className="text-sm font-sans">Solutions</a>
          <a href="#" className="text-sm font-sans">Pricing</a>
          <a href="#" className="text-sm font-sans">Login</a>
          <a href="/dashboard" className="px-5 py-2 rounded-full border-2 border-foreground text-sm font-semibold font-sans text-center">GET STARTED</a>
        </div>
      )}
    </nav>
  );
};

export default Navbar;
