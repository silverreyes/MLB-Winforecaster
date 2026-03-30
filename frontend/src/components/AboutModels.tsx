import styles from './AboutModels.module.css';

export function AboutModels() {
  return (
    <div className={styles.container}>
      <details className={styles.details}>
        <summary className={styles.summary}>
          <span className={styles.summaryText}>About the Models</span>
          <span className={styles.chevron} aria-hidden="true">{'\u25B6'}</span>
        </summary>
        <div className={styles.content}>
          <section className={styles.section}>
            <h3 className={styles.heading}>Model Types</h3>
            <ul className={styles.list}>
              <li><strong>Logistic Regression (LR)</strong> — A linear model that weights each stat (win rate, ERA, etc.) to estimate win probability. Simple and interpretable.</li>
              <li><strong>Random Forest (RF)</strong> — Builds hundreds of decision trees on random subsets of the data, then averages their predictions. Handles complex stat interactions.</li>
              <li><strong>XGBoost (XGB)</strong> — Builds decision trees sequentially, with each tree correcting the previous ones' errors. Often the most accurate on structured data.</li>
            </ul>
            <p className={styles.paragraph}>The <strong>ensemble</strong> probability shown on each card averages all three models for a more stable estimate.</p>
          </section>

          <section className={styles.section}>
            <h3 className={styles.heading}>Reading the Probabilities</h3>
            <p className={styles.paragraph}>A probability of <strong>68%</strong> means the home team wins in roughly 68 out of 100 similar matchups.</p>
          </section>

          <section className={styles.section}>
            <h3 className={styles.heading}>Calibration</h3>
            <p className={styles.paragraph}>These models are <em>calibrated</em>: when they say 70%, the home team has historically won about 70% of the time. The Brier scores above measure calibration accuracy (lower is better).</p>
          </section>

          <section className={styles.section}>
            <h3 className={styles.heading}>PRE-LINEUP vs. POST-LINEUP</h3>
            <p className={styles.paragraph}><strong>PRE-LINEUP</strong> predictions use only team-level stats (win rate, run differential, etc.) and carry more uncertainty. <strong>POST-LINEUP</strong> predictions incorporate confirmed starting pitcher data and are the primary signal.</p>
          </section>

          <section className={styles.section}>
            <h3 className={styles.heading}>Kalshi Market Prices</h3>
            <p className={styles.paragraph}>Kalshi is a regulated prediction market where contracts pay $1 if an outcome occurs. A price of 62c implies the market estimates a 62% chance the home team wins. The edge signal compares model probability against market price.</p>
            <p className={styles.disclaimer}>Kalshi charges a 7% fee on net profits. Displayed prices do not account for this fee. Nothing on this dashboard is trading advice or a recommendation to buy or sell contracts.</p>
          </section>
        </div>
      </details>
    </div>
  );
}
