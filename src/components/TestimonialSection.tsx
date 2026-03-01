const TestimonialSection = () => {
  return (
    <section className="py-24 bg-foreground text-background">
      <div className="max-w-5xl mx-auto px-6 text-center">
        <blockquote className="font-serif text-3xl md:text-4xl lg:text-5xl font-normal leading-tight mb-8">
          "Friendly called 5 plumbers for me in 30 seconds and got me the best quote. I never want to make a phone call again."
        </blockquote>
        <p className="font-sans text-sm text-background/60 mb-16">
          — Dan Westfall CFP®, CFS®, Founder, Client Focused Financial
        </p>

        <div className="flex flex-col sm:flex-row justify-center gap-20 mb-16">
          <div className="text-center">
            <div className="font-serif text-6xl font-normal text-background mb-2">30s</div>
            <div className="font-sans text-sm text-background/60">Average time to get multiple quotes</div>
          </div>
          <div className="text-center">
            <div className="font-serif text-6xl font-normal text-background mb-2">5+</div>
            <div className="font-sans text-sm text-background/60">Calls made in parallel for you</div>
          </div>
        </div>

        <img
          src="https://cdn.prod.website-files.com/66563d83090173fa830e5776/699f429a7f9d1615996af23c_testimonial-laptop.avif"
          alt="Testimonial"
          className="w-full max-w-3xl mx-auto rounded-2xl object-cover mb-12"
        />

        <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
          <button className="px-6 py-3 rounded-full border-2 border-background bg-transparent text-sm font-semibold font-sans hover:bg-background hover:text-foreground transition-colors text-background">
            Get Demo
          </button>
          <a
            href="#"
            className="px-6 py-3 rounded-full bg-[hsl(var(--accent))] text-foreground text-sm font-semibold font-sans hover:opacity-80 transition-opacity"
          >
            Try Friendly Free
          </a>
        </div>
      </div>
    </section>
  );
};

export default TestimonialSection;
