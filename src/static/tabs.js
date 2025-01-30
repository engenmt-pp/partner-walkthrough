// This code is inspired by the excellent blog post by Mayank: https://www.mayank.co/blog/tabs/

class TheTabs extends HTMLElement {
  get tabs() {
    return [...this.querySelectorAll("[role=tab]")];
  }

  get panels() {
    return [...this.querySelectorAll("[role=tabpanel]")];
  }

  get selected() {
    return this.querySelector("[role=tab][aria-selected=true]");
  }

  set selected(element) {
    this.selected?.setAttribute("aria-selected", "false");
    element?.setAttribute("aria-selected", "true");
    element?.focus();
    this.updateSelection();
  }

  connectedCallback() {
    this.generateIds();
    this.updateSelection();
    this.setupEvents();
  }

  generateIds() {
    const prefix = Math.floor(Date.now()).toString(36);

    this.tabs.forEach((tab, index) => {
      const panel = this.panels[index];

      tab.id ||= `${prefix}-tab-${index}`;
      panel.id ||= `${prefix}-panel-${index}`;

      tab.setAttribute("aria-controls", panel.id);
      panel.setAttribute("aria-labelledby", tab.id);
    });
  }

  updateSelection() {
    this.tabs.forEach((tab, index) => {
      const panel = this.panels[index];
      const isSelected = tab.getAttribute("aria-selected") === "true";

      tab.setAttribute("aria-selected", isSelected ? "true" : "false");
      tab.setAttribute("tabindex", isSelected ? "0" : "-1");
      panel.setAttribute("tabindex", isSelected ? "0" : "-1");
      panel.hidden = !isSelected;
    });
  }

  setupEvents() {
    this.tabs.forEach((tab) => {
      tab.addEventListener("click", () => (this.selected = tab));

      tab.addEventListener("keydown", (e) => {
        switch (e.key) {
          case "ArrowLeft":
            this.selected = tab.previousElementSibling ?? this.tabs.at(-1);
            break;
          case "ArrowRight":
            this.selected = tab.nextElementSibling ?? this.tabs.at(0);
            break;
          case "ArrowUp":
            const outerTabs = document.querySelector("the-tabs:not(the-tabs the-tabs)");
            if (this !== outerTabs) {
              outerTabs.selected.focus();
              e.preventDefault();
            }
            break;
          case "ArrowDown":
            const innerTabs = this.querySelector("the-tabs");
            if (innerTabs) {
              innerTabs.selected.focus();
              e.preventDefault();
            }
            break;
        }
      });
    });
  }
}

export { TheTabs as default };
