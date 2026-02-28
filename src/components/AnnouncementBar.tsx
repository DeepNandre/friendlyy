import { ArrowRight } from "lucide-react";

const AnnouncementBar = () => {
  return (
    <div className="bg-[hsl(var(--accent))] px-4 py-3 flex items-center justify-between">
      <div className="flex items-center gap-2 text-sm font-medium text-foreground mx-auto">
        <span className="font-semibold font-sans">New in Quin:</span>
        <span className="font-sans">Introducing workflows, built to automate your workday.</span>
        <a href="#" className="flex items-center gap-1 font-semibold font-sans uppercase text-xs tracking-wide hover:underline ml-2">
          Read <ArrowRight className="w-3 h-3" />
        </a>
      </div>
    </div>
  );
};

export default AnnouncementBar;
