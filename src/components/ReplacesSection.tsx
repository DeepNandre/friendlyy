const tasks = [
  "Calling for quotes", "Waiting on hold", "Navigating phone menus",
  "Canceling subscriptions", "Booking appointments", "Negotiating bills",
  "Comparing prices", "Finding availability", "Following up",
];

const ReplacesSection = () => {
  return (
    <section className="py-20 bg-background overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 text-center">
        <h2 className="font-serif text-4xl md:text-6xl font-normal text-foreground mb-12 leading-tight">
          Never do these again
        </h2>

        <div className="flex flex-wrap justify-center gap-3">
          {tasks.map((task, i) => (
            <div
              key={i}
              className="px-5 py-2.5 rounded-full border border-border text-sm font-sans text-foreground line-through opacity-60"
            >
              {task}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default ReplacesSection;
