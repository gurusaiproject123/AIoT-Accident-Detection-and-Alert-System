import { Link } from "react-router";
import Icon from "../components/Icon";
import { EmptyState, Panel } from "../components/ui";
import { BASE_PATH } from "../data";

export default function NotFound() {
  return (
    <div className="su-page">
      <Panel>
        <EmptyState icon="search" title="Page not found">
          This superuser page does not exist. Use the navigation to continue.
        </EmptyState>
        <div className="su-center">
          <Link to={BASE_PATH} className="su-btn su-btn-soft">
            <Icon name="chevronLeft" size={15} /> Back to overview
          </Link>
        </div>
      </Panel>
    </div>
  );
}

