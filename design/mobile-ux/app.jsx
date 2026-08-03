/* global DesignCanvas, DCSection, DCArtboard */
/* global IntroCard, GestureMap */
/* global MockA_SkyFirstHUD, MockC_MiniRail, MockLanding */
/* global MockE_Cinema, MockF_SideRail */

function App() {
  return (
    <DesignCanvas title="BCF · Mobile UX v2" background="#050709">
      <DCSection id="intro" title="Intro" subtitle="What changed in this revision">
        <DCArtboard id="intro-card" label="System notes" width={820} height={460}>
          <div style={{ padding: 30, height: "100%", boxSizing: "border-box", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <IntroCard />
          </div>
        </DCArtboard>
      </DCSection>

      <DCSection id="landing" title="Landing / interstitial" subtitle="First impression — surfaces credits + a help button on every device">
        <DCArtboard id="landing-default" label="Landing · default" width={410} height={864}>
          <MockLanding />
        </DCArtboard>
        <DCArtboard id="landing-help" label="Landing · help overlay" width={410} height={864}>
          <MockLanding helpOpen />
        </DCArtboard>
      </DCSection>

      <DCSection id="portrait" title="Portrait (kept directions)" subtitle="A and C — moving forward">
        <DCArtboard id="A" label="A · Sky-first HUD" width={410} height={864}>
          <MockA_SkyFirstHUD />
        </DCArtboard>
        <DCArtboard id="C" label="C · Mini-rail bottom" width={410} height={864}>
          <MockC_MiniRail />
        </DCArtboard>
      </DCSection>

      <DCSection id="landscape" title="Landscape" subtitle="E cinema (kept) + F side-rail reworked">
        <DCArtboard id="F-default" label="F · Side rail v2" width={864} height={410}>
          <MockF_SideRail />
        </DCArtboard>
        <DCArtboard id="F-gear" label="F · Settings flyout" width={864} height={410}>
          <MockF_SideRail flyout="gear" />
        </DCArtboard>
        <DCArtboard id="F-info" label="F · Credits flyout" width={864} height={410}>
          <MockF_SideRail flyout="info" />
        </DCArtboard>
        <DCArtboard id="F-hidden" label="F · Chrome auto-hidden" width={864} height={410}>
          <MockF_SideRail chromeVisible={false} />
        </DCArtboard>
        <DCArtboard id="E" label="E · Cinema (reference)" width={864} height={410}>
          <MockE_Cinema chromeVisible />
        </DCArtboard>
      </DCSection>

      <DCSection id="gesture" title="Touch contract" subtitle="Shared by every direction above">
        <DCArtboard id="gestures" label="Gesture map" width={820} height={620}>
          <div style={{ padding: 30, height: "100%", boxSizing: "border-box", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <GestureMap />
          </div>
        </DCArtboard>
      </DCSection>
    </DesignCanvas>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
