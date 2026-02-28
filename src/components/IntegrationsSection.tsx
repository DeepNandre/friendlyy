const integrations = [
  { name: "DocuSign", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/69a0671af9896b0838abe6f3_docusign.png" },
  { name: "Box", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/698b5d10189870fe0b0c1ebf_box.png" },
  { name: "Zendesk", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/696122be08f89189c92dac27_zendesk.png" },
  { name: "Zapier", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/695550698bf779988cf4df7a_zapier.png" },
  { name: "Knudge", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/6939935c7fe5b545cb68403b_knudge.png" },
  { name: "ClickUp", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/6931d7068342b819684f1df5_clickup.png" },
  { name: "RingCentral", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/6931d26e6b0515940aa3b680_ringcentral.png" },
  { name: "Zoom Phone", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/69249abb3a82c585663379ee_zoom-phone.png" },
  { name: "Google Drive", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/691f53ddf105f6bd2c6efbc3_google_drive.png" },
  { name: "Asana", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/68fb90438b21300081b48bb3_asana.png" },
  { name: "Dex", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/68f938f3e59eb43e656dbc2c_dex.png" },
  { name: "Google Tasks", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/68f8fa09afe3c050d07541ee_google_tasks.png" },
  { name: "Google Meet", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/68c82ba934755704ad41af1c_google-meet.png" },
  { name: "Zoho CRM", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/68c4307f3f37598c1fa5f5a2_zoho-crm.png" },
  { name: "HubSpot", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/68c2f6ee592b15474b697a33_hubspot.png" },
  { name: "Outlook", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/688bbb2ad7a872750f2f2d9b_outlook.png" },
  { name: "Google Calendar", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/688bbb620dacb2b7b34f2188_google-calendar.png" },
  { name: "Teams", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/688bbb9ef11a9cf69f714a9e_teams.png" },
  { name: "Gmail", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/688bbbc1bedd990f90f8d4ab_gmail.png" },
  { name: "Slack", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/688bbc1afbd0ee4629ad6e06_slack.png" },
  { name: "Zoom", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/688bbc42eca512ec3856fead_zoom.png" },
  { name: "Redtail", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/68f7e26045bf3b06be22dbca_redtail.png" },
  { name: "Wealthbox", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/688bbc690f4c0d051e821138_wealthbox.png" },
  { name: "Pipedrive", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/688bbb14d1a172fbe315d084_pipedrive.png" },
  { name: "Salesforce", img: "https://cdn.prod.website-files.com/669ff68abc567b75ddd963bd/688ba8241e48d48e644a4450_salesforce.png" },
];

const IntegrationsSection = () => {
  const doubled = [...integrations, ...integrations];

  return (
    <section className="py-20 bg-background overflow-hidden">
      <div className="max-w-7xl mx-auto px-6 text-center mb-10">
        <h2 className="font-serif text-3xl md:text-4xl font-normal text-foreground mb-2">
          Get started with the tools you're already using
        </h2>
      </div>

      {/* Marquee Row 1 */}
      <div className="relative flex overflow-hidden mb-4">
        <div className="flex animate-marquee gap-6 items-center">
          {doubled.map((item, i) => (
            <div key={i} className="flex-shrink-0 w-16 h-16 bg-card rounded-xl shadow-sm border border-border flex items-center justify-center p-2">
              <img src={item.img} alt={item.name} className="max-w-full max-h-full object-contain" />
            </div>
          ))}
        </div>
      </div>

      {/* Marquee Row 2 (reverse) */}
      <div className="relative flex overflow-hidden">
        <div className="flex animate-marquee-reverse gap-6 items-center">
          {[...doubled].reverse().map((item, i) => (
            <div key={i} className="flex-shrink-0 w-16 h-16 bg-card rounded-xl shadow-sm border border-border flex items-center justify-center p-2">
              <img src={item.img} alt={item.name} className="max-w-full max-h-full object-contain" />
            </div>
          ))}
        </div>
      </div>

      <div className="text-center mt-10">
        <a href="#" className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border-2 border-foreground text-sm font-semibold font-sans hover:bg-foreground hover:text-background transition-colors">
          See all integrations →
        </a>
      </div>
    </section>
  );
};

export default IntegrationsSection;
