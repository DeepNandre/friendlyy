import { useState } from "react";
import AnnouncementBar from "@/components/AnnouncementBar";
import Navbar from "@/components/Navbar";
import HeroSection from "@/components/HeroSection";
import SkillsSection from "@/components/SkillsSection";
import IntegrationsSection from "@/components/IntegrationsSection";
import SolutionsSection from "@/components/SolutionsSection";
import IntelligenceSection from "@/components/IntelligenceSection";
import TestimonialSection from "@/components/TestimonialSection";
import TalkToQuin from "@/components/TalkToQuin";
import SecuritySection from "@/components/SecuritySection";
import ReplacesSection from "@/components/ReplacesSection";
import PricingSection from "@/components/PricingSection";
import Footer from "@/components/Footer";

const Index = () => {
  return (
    <div className="min-h-screen bg-background">
      <AnnouncementBar />
      <Navbar />
      <HeroSection />
      <SkillsSection />
      <IntegrationsSection />
      <SolutionsSection />
      <IntelligenceSection />
      <TestimonialSection />
      <TalkToQuin />
      <SecuritySection />
      <ReplacesSection />
      <PricingSection />
      <Footer />
    </div>
  );
};

export default Index;
