using System.Drawing.Drawing2D;

internal sealed class StudioTitleBar : Panel
{
    readonly StudioWindow owner;
    readonly CaptionButton sidebar, minimize, maximize, close;
    readonly ToolTip tips = new() { InitialDelay = 550, ReshowDelay = 150 };
    bool active = true;

    public StudioTitleBar(StudioWindow owner, Action toggleSidebar)
    {
        this.owner=owner;
        Dock=DockStyle.Top;
        Height=48;
        BackColor=Color.White;
        DoubleBuffered=true;
        sidebar=Add(CaptionGlyph.Sidebar,"收起侧栏",toggleSidebar);
        minimize=Add(CaptionGlyph.Minimize,"最小化",()=>owner.WindowState=FormWindowState.Minimized);
        maximize=Add(CaptionGlyph.Maximize,"最大化",owner.ToggleMaximize);
        close=Add(CaptionGlyph.Close,"关闭",owner.Close);
    }

    CaptionButton Add(CaptionGlyph glyph,string label,Action action)
    {
        var button=new CaptionButton(glyph){AccessibleName=label,TabStop=false};
        button.Click+=(_,_)=>action();Controls.Add(button);tips.SetToolTip(button,label);return button;
    }
    int Px(float value)=>(int)Math.Round(value*DeviceDpi/96f);

    protected override void OnLayout(LayoutEventArgs e)
    {
        base.OnLayout(e);
        if(close==null)return;
        Height=Px(48);
        sidebar.SetBounds(Px(14),Px(7),Px(36),Px(34));
        var width=Px(48);
        close.SetBounds(ClientSize.Width-width,0,width,Height);
        maximize.SetBounds(ClientSize.Width-width*2,0,width,Height);
        minimize.SetBounds(ClientSize.Width-width*3,0,width,Height);
    }
    protected override void OnDpiChangedAfterParent(EventArgs e){base.OnDpiChangedAfterParent(e);PerformLayout();Invalidate(true);}
    internal void SetActive(bool value){active=value;Invalidate();}
    internal void RefreshWindowState()
    {
        if(maximize==null)return;
        maximize.Glyph=owner.WindowState==FormWindowState.Maximized?CaptionGlyph.Restore:CaptionGlyph.Maximize;
        maximize.AccessibleName=maximize.Glyph==CaptionGlyph.Restore?"还原":"最大化";
        tips.SetToolTip(maximize,maximize.AccessibleName);maximize.Invalidate();
    }
    internal void SetSidebarCollapsed(bool collapsed)
    {
        sidebar.Collapsed=collapsed;sidebar.AccessibleName=collapsed?"展开侧栏":"收起侧栏";
        tips.SetToolTip(sidebar,sidebar.AccessibleName);sidebar.Invalidate();
    }
    protected override void OnPaint(PaintEventArgs e)
    {
        base.OnPaint(e);
        using var divider=new Pen(Color.FromArgb(231,231,231));
        e.Graphics.DrawLine(divider,Px(64),Px(17),Px(64),Px(31));
        using var font=new Font("Segoe UI",10f,FontStyle.Regular);
        TextRenderer.DrawText(e.Graphics,"Qwen Studio",font,new Rectangle(Px(80),0,Px(190),Height),
            active?Color.FromArgb(48,48,48):Color.FromArgb(128,128,128),TextFormatFlags.Left|TextFormatFlags.VerticalCenter|TextFormatFlags.NoPadding);
        using var baseline=new Pen(Color.FromArgb(244,244,244));
        e.Graphics.DrawLine(baseline,0,Height-1,Width,Height-1);
    }
    protected override void Dispose(bool disposing){if(disposing)tips.Dispose();base.Dispose(disposing);}
    protected override void WndProc(ref Message m)
    {
        // Let Windows handle caption dragging, double-click and drag-to-restore.
        // Child buttons keep their own hit areas; only the empty bar passes through.
        if(m.Msg==0x84){m.Result=(IntPtr)(-1);return;}
        base.WndProc(ref m);
    }
}

internal enum CaptionGlyph { Sidebar, Minimize, Maximize, Restore, Close }

internal sealed class CaptionButton : Button
{
    internal CaptionGlyph Glyph;
    internal bool Collapsed;
    bool hover,pressed;
    public CaptionButton(CaptionGlyph glyph)
    {
        Glyph=glyph;FlatStyle=FlatStyle.Flat;FlatAppearance.BorderSize=0;
        BackColor=Color.White;Cursor=Cursors.Default;
        SetStyle(ControlStyles.UserPaint|ControlStyles.AllPaintingInWmPaint|ControlStyles.OptimizedDoubleBuffer,true);
    }
    protected override void OnMouseEnter(EventArgs e){hover=true;Invalidate();base.OnMouseEnter(e);}
    protected override void OnMouseLeave(EventArgs e){hover=false;pressed=false;Invalidate();base.OnMouseLeave(e);}
    protected override void OnMouseDown(MouseEventArgs e){pressed=e.Button==MouseButtons.Left;Invalidate();base.OnMouseDown(e);}
    protected override void OnMouseUp(MouseEventArgs e){pressed=false;Invalidate();base.OnMouseUp(e);}
    protected override void OnPaint(PaintEventArgs e)
    {
        var g=e.Graphics;g.Clear(BackColor);
        float scale=DeviceDpi/96f;
        g.SmoothingMode=SmoothingMode.AntiAlias;
        bool highlight=hover;
        var foreground=Color.FromArgb(76,76,76);
        if(highlight){
            var fill=Glyph==CaptionGlyph.Close?(pressed?Color.FromArgb(195,35,49):Color.FromArgb(222,48,62)):
                pressed?Color.FromArgb(229,229,229):Color.FromArgb(241,241,241);
            using var brush=new SolidBrush(fill);
            if(Glyph==CaptionGlyph.Sidebar){using var shape=Rounded(new RectangleF(0,0,Width,Height),8*scale);g.FillPath(brush,shape);}
            else g.FillRectangle(brush,ClientRectangle);
            if(Glyph==CaptionGlyph.Close)foreground=Color.White;
        }
        g.TranslateTransform(Width/2f,Height/2f);g.ScaleTransform(scale,scale);
        using var pen=new Pen(foreground,Glyph==CaptionGlyph.Sidebar?1.45f:1.15f){StartCap=LineCap.Round,EndCap=LineCap.Round,LineJoin=LineJoin.Round};
        switch(Glyph){
            case CaptionGlyph.Sidebar:
                using(var outline=Rounded(new RectangleF(-8,-7,16,14),2))g.DrawPath(pen,outline);
                if(!Collapsed){using var shade=new SolidBrush(Color.FromArgb(225,225,225));g.FillRectangle(shade,-6.9f,-5.9f,4.2f,11.8f);}
                g.DrawLine(pen,-2.5f,-6.5f,-2.5f,6.5f);break;
            case CaptionGlyph.Minimize:g.DrawLine(pen,-5,0,5,0);break;
            case CaptionGlyph.Maximize:g.DrawRectangle(pen,-4.5f,-4.5f,9,9);break;
            case CaptionGlyph.Restore:
                g.DrawLines(pen,[new(-2,-5),new(5,-5),new(5,2)]);
                g.DrawRectangle(pen,-5,-2,7,7);break;
            case CaptionGlyph.Close:g.DrawLine(pen,-4.5f,-4.5f,4.5f,4.5f);g.DrawLine(pen,-4.5f,4.5f,4.5f,-4.5f);break;
        }
    }
    static GraphicsPath Rounded(RectangleF r,float radius)
    {
        var path=new GraphicsPath();var d=radius*2;
        path.AddArc(r.Left,r.Top,d,d,180,90);path.AddArc(r.Right-d,r.Top,d,d,270,90);
        path.AddArc(r.Right-d,r.Bottom-d,d,d,0,90);path.AddArc(r.Left,r.Bottom-d,d,d,90,90);path.CloseFigure();return path;
    }
}
