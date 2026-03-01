interface FriendlyLogoProps {
  /** Use "invert" for dark backgrounds (e.g. footer) */
  variant?: "default" | "invert";
  /** Icon only, or full wordmark (icon + text) */
  type?: "wordmark" | "icon";
  size?: "sm" | "md" | "lg";
  className?: string;
}

const FriendlyLogo = ({
  variant = "default",
  type = "wordmark",
  size = "md",
  className = "",
}: FriendlyLogoProps) => {
  const invertClass = variant === "invert" ? "brightness-0 invert" : "";
  const sizeClasses = {
    sm: type === "icon" ? "h-6 w-6" : "h-6",
    md: type === "icon" ? "h-8 w-8" : "h-8",
    lg: type === "icon" ? "h-10 w-10" : "h-10",
  };

  const src =
    type === "icon"
      ? "/friendly-logo-monochrome.jpg"
      : "/friendly-wordmark-monochrome.jpg";

  return (
    <img
      src={src}
      alt="Friendly"
      className={`${invertClass} ${sizeClasses[size]} ${type === "wordmark" ? "w-auto object-contain object-left" : "object-contain"} ${className}`}
    />
  );
};

export default FriendlyLogo;
