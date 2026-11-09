import { useEffect } from "react";
import BuyerLink from "../components/home/BuyerLink";
import Facts from "../components/home/Facts";
import Features from "../components/home/Features";
import Hero from "../components/home/Hero";
import HomeFooter from "../components/home/HomeFooter";
import HomeNav from "../components/home/HomeNav";
import Problem from "../components/home/Problem";
import Roles from "../components/home/Roles";
import StageSheet from "../components/home/StageSheet";
import "../components/home/home.css";

/** The public home page. It holds no data: it explains the product and sends each person to the right door. */
export default function Landing() {
  useEffect(() => {
    document.title = "LoomTrack · Knitwear production tracking";
  }, []);

  return (
    <div className="home">
      <HomeNav />
      <main>
        <Hero />
        <Facts />
        <Problem />
        <Roles />
        <StageSheet />
        <Features />
        <BuyerLink />
      </main>
      <HomeFooter />
    </div>
  );
}
