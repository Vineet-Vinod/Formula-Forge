using UnrealBuildTool;

public class FormulaForgeEditorTarget : TargetRules
{
    public FormulaForgeEditorTarget(TargetInfo target) : base(target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V7;
        IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
        ExtraModuleNames.Add("FormulaForge");
    }
}
