// Copyright (c) Microsoft Corporation.
// Licensed under the MIT License.

import React from "react";
import { cn } from "../libs/utils";

interface PaneProps extends React.HTMLAttributes<HTMLDivElement> {}

export const Pane = React.forwardRef<HTMLDivElement, PaneProps>(
  ({ children, className }, ref) => {
    return (
      <div
        ref={ref}
        className={cn(
          "bg-background flex-1 p-4 border-2 border-gray-300 rounded-md overflow-y-auto flex flex-col",
          className
        )}
      >
        {children}
      </div>
    );
  }
);
Pane.displayName = "Pane";
