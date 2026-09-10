-- SPDX-License-Identifier: MIT
-- Disposable adapter for exact qualified SDK; never a product authority.
with Ada.Command_Line; with Ada.Text_IO;
with Interfaces.C;
with MC_Clock; with MC_FS; with MC_Hex; with MC_Posix; with MC_Runtime;
with MC_SHA256; with MC_Store; with MC_Types; use MC_Types;
with Pkg_Supply_Map;
procedure Map_Chaos_Driver with SPARK_Mode => Off is
   Store : MC_Store.Store; Media : MC_FS.Root; File : MC_FS.File;
   Status : Outcome; Target : Pkg_Supply_Map.Context;
   Items : Pkg_Supply_Map.Sources (1 .. 1); Trusted : Pkg_Supply_Map.Authorities (1 .. 1);
   Wire : Bytes (1 .. 257); Used : Natural;
   Expected, Address : Digest := Zero_Digest; Now, Boot, Deadline, Until_Time : Counter := 0;
   Stop : exception;
   use type Interfaces.C.unsigned;
   procedure Need (Label_Text : String) is
   begin
      if Status /= OK then Ada.Text_IO.Put_Line ("FAIL " & Label_Text & " " & Outcome'Image (Status)); raise Stop; end if;
   end Need;
   procedure Read (Name : String; Data : out Bytes) is
   begin
      MC_FS.Open_Read (Media, Name, File, Status); Need ("fixture open");
      MC_FS.Read_At (File, 0, Data, Used, Status); MC_FS.Close (File); Need ("fixture read");
   end Read;
begin
   if Ada.Command_Line.Argument_Count /= 4 or else MC_Posix.Euid = 0 then raise Stop; end if;
   MC_Runtime.Initialize (Status); Need ("runtime");
   MC_Store.Open (Ada.Command_Line.Argument (2), Store, Status); Need ("reopen");
   MC_FS.Open_Root (Ada.Command_Line.Argument (3), Media, Status); Need ("media");
   Read ("map", Wire); if Used /= 256 then raise Stop; end if;
   Expected := MC_SHA256.Hash (Wire (1 .. 256));
   Target.Root_ID := (others => 104); Target.Catalog := Wire (89 .. 120); Target.Closure := Wire (121 .. 152);
   Items (1) := (Wire (161 .. 192), Wire (193 .. 224), Wire (225 .. 256));
   Read ("public-key", Trusted (1).Key); if Used /= 32 then raise Stop; end if;
   Read ("scope", Trusted (1).Scope); if Used /= 32 then raise Stop; end if;
   Trusted (1).Minimum_Epoch := 7; Trusted (1).Maximum_Age := 1_800;
   MC_Clock.Realtime_Seconds (Now, Status); Need ("UTC");
   MC_Clock.Boottime_Milliseconds (Boot, Status); Need ("boottime");
   Deadline := Boot + Counter'Value (Ada.Command_Line.Argument (4));
   Ada.Text_IO.Put_Line ("READY " & Ada.Command_Line.Argument (1)); Ada.Text_IO.Flush;
   if Ada.Command_Line.Argument (1) = "prepare" then
      Pkg_Supply_Map.Prepare (Store, Target, Items, Trusted, Now, Deadline, Address, Until_Time, Status);
   elsif Ada.Command_Line.Argument (1) = "verify" then
      Pkg_Supply_Map.Verify (Store, Expected, Target, Trusted, Now, Deadline, Until_Time, Status);
      if Status = OK then Address := Expected; end if;
   elsif Ada.Command_Line.Argument (1) = "retention" then
      Pkg_Supply_Map.Check_Retention (Store, Expected, Target.Catalog, Target.Closure, Deadline, Status);
      if Status = OK then Address := Expected; end if;
   else raise Stop;
   end if;
   if (Status = OK and then Address /= Expected) or else
      (Status /= OK and then (Address /= Zero_Digest or else Until_Time /= 0)) then
      Ada.Text_IO.Put_Line ("VIOLATION stale success output"); raise Stop;
   end if;
   Ada.Text_IO.Put_Line ("RESULT " & Outcome'Image (Status) & " " & MC_Hex.Encode (Address) & Counter'Image (Until_Time));
   if Status /= OK then Ada.Command_Line.Set_Exit_Status (10); end if;
   MC_FS.Close (Media); MC_Store.Close (Store);
exception when Stop => MC_FS.Close (File); MC_FS.Close (Media); MC_Store.Close (Store); Ada.Command_Line.Set_Exit_Status (11);
end Map_Chaos_Driver;
