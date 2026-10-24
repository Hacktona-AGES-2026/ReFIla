import { useEffect, useState } from "react";
import DoctorApp from "./components/DoctorApp";
import HowItWorks from "./components/HowItWorks";
import Landing from "./components/Landing";
import PatientPortal from "./components/PatientPortal";

const ROUTES = { "#/medico": DoctorApp, "#/paciente": PatientPortal, "#/como-funciona": HowItWorks };

export default function App() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const onChange = () => { setHash(window.location.hash); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const Page = ROUTES[hash] ?? Landing;
  return <Page />;
}
